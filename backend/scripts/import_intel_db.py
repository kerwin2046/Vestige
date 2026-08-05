"""Import competitive-intel intel.db items into Vestige SQLite for browsing.

Creates/updates companies and one succeeded run per competitor with items as
run_sources. Sentiment/themes/source live in detail JSON.

Usage (repo root):
  make import-intel
  PYTHONPATH=backend python3 -m scripts.import_intel_db --dry-run
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select

from database import Database
from models import Company, Run, RunStatus, utc_now
from repositories import runs as runs_repo

DEFAULT_INTEL_DB = Path.home() / ".openclaw/workspace/competitive-intel/intel.db"

# Display name + optional official domain for known competitors.
COMPETITOR_META: dict[str, dict[str, str]] = {
    "Protolabs": {"domain": "protolabs.com"},
    "protolabs": {"name": "Protolabs", "domain": "protolabs.com"},
    "protolabs_network": {"name": "Protolabs", "domain": "protolabs.com"},
    "Xometry": {"domain": "xometry.com"},
    "Fictiv": {"domain": "fictiv.com"},
    "RapidDirect": {"domain": "rapiddirect.com"},
    "WayKen": {"name": "WayKen", "domain": "waykenrm.com"},
    "waykenrm": {"name": "WayKen", "domain": "waykenrm.com"},
    "Unionfab": {"domain": "unionfab.com"},
    "嘉立创": {"domain": "jlcpcb.com"},
    "PCBWay": {"domain": "pcbway.com"},
    "FastPreci": {"domain": "fastpreci.com"},
    "Baosheng": {"domain": "baoshengindustry.com"},
    "通用": {"domain": ""},
}

CATEGORY_TO_SOURCE_TYPE = {
    "review": "community_ugc",
    "forum": "community_ugc",
    "employee": "recruitment",
    "competitor_blog": "owned",
    "official": "owned",
    "ir": "public_record",
    "video": "social",
    "dev": "academic_technical",
    "finance": "public_record",
    "media": "news_media",
    "analyst": "news_media",
    "customer_story": "reference",
    "directory": "marketplace_directory",
    "blog": "other",
    "chinese": "other",
    "procurement": "public_record",
    "other": "other",
}


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def _host_of(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def _normalize_domain(value: str | None) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = f"//{value}"
    host = urlsplit(value).hostname or ""
    return host.removeprefix("www.")


def resolve_competitor(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip() or "未知"
    meta = COMPETITOR_META.get(raw) or COMPETITOR_META.get(raw.casefold()) or {}
    name = meta.get("name") or raw
    domain = meta.get("domain", "")
    return name, domain


def map_source_type(category: str, source: str) -> str:
    if source == "trustpilot":
        return "community_ugc"
    if source in {"youtube", "bili"}:
        return "social"
    if source == "sec":
        return "public_record"
    if source == "github":
        return "academic_technical"
    return CATEGORY_TO_SOURCE_TYPE.get(category or "other", "other")


def map_ownership(category: str) -> str:
    if category in {"competitor_blog", "official", "ir"}:
        return "first_party"
    if category in {"review", "forum", "media", "analyst", "employee"}:
        return "third_party"
    return "unknown"


def load_items(intel_db: Path) -> dict[str, list[dict]]:
    conn = sqlite3.connect(intel_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT url, title, source, category, competitor, published,
                   snippet, sentiment, themes, first_seen
            FROM items
            ORDER BY id
            """
        ).fetchall()
    finally:
        conn.close()

    grouped: dict[str, list[dict]] = defaultdict(list)
    seen_urls: set[str] = set()
    for row in rows:
        url = (row["url"] or "").strip()
        if not url.startswith("http") or url in seen_urls:
            continue
        seen_urls.add(url)
        name, domain = resolve_competitor(row["competitor"] or "")
        grouped[name].append(
            {
                "url": url,
                "canonical_url": url,
                "domain": _host_of(url),
                "source_type": map_source_type(row["category"] or "", row["source"] or ""),
                "ownership": map_ownership(row["category"] or ""),
                "confidence": 0.6 if row["sentiment"] else 0.4,
                "title": row["title"] or "",
                "snippet": row["snippet"] or "",
                "discovery_path": f"competitive-intel/{row['source'] or 'unknown'}",
                "bfs_round": 0,
                "detail": {
                    "imported_from": "competitive-intel",
                    "collector": row["source"],
                    "category": row["category"],
                    "published": row["published"],
                    "sentiment": row["sentiment"],
                    "themes": row["themes"],
                    "first_seen": row["first_seen"],
                    "competitor_raw": row["competitor"],
                    "official_domain_hint": domain,
                },
            }
        )
    return grouped


def find_company(session, *, name: str, domain: str) -> Company | None:
    companies = list(session.scalars(select(Company)))
    if domain:
        for company in companies:
            if _normalize_domain(company.official_domain) == domain:
                return company
    needle = name.casefold()
    for company in companies:
        if company.name.casefold() == needle:
            return company
        if needle in {a.casefold() for a in (company.aliases or [])}:
            return company
    return None


def get_or_create_company(session, *, name: str, domain: str) -> Company:
    company = find_company(session, name=name, domain=domain)
    if company is None:
        company = Company(
            id=str(uuid4()),
            name=name,
            official_domain=domain,
            industry="",
            location="",
            aliases=[],
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        return company

    changed = False
    if domain and not company.official_domain:
        company.official_domain = domain
        changed = True
    if name.casefold() != company.name.casefold():
        aliases = list(company.aliases or [])
        if name.casefold() not in {a.casefold() for a in aliases}:
            aliases.append(name)
            company.aliases = aliases
            changed = True
    if company.name.islower() and not name.islower() and company.name.casefold() == name.casefold():
        company.name = name
        changed = True
    if changed:
        company.updated_at = utc_now()
        session.commit()
        session.refresh(company)
    return company


def already_imported(session, *, company_id: str, export_path: str) -> bool:
    existing = list(
        session.scalars(
            select(Run).where(Run.company_id == company_id, Run.export_path == export_path)
        )
    )
    return bool(existing)


def import_intel(intel_db: Path, *, dry_run: bool = False) -> int:
    if not intel_db.exists():
        print(f"intel.db not found: {intel_db}")
        return 1

    grouped = load_items(intel_db)
    print(f"intel_db={intel_db}")
    print(f"competitors={len(grouped)} items={sum(len(v) for v in grouped.values())}")

    database = Database(_database_url())
    database.create_all()

    imported = skipped = 0
    with database.session_factory() as session:
        for name, sources in sorted(grouped.items(), key=lambda x: x[0].casefold()):
            domain = ""
            for item in sources:
                hint = (item.get("detail") or {}).get("official_domain_hint") or ""
                if hint:
                    domain = hint
                    break
            # Prefer meta domain
            _, meta_domain = resolve_competitor(name)
            domain = meta_domain or domain

            export_path = f"competitive-intel/intel.db#{name}"
            if dry_run:
                print(f"  dry-run {name:16} domain={domain or '-':20} sources={len(sources)}")
                imported += 1
                continue

            company = get_or_create_company(session, name=name, domain=domain)
            if already_imported(session, company_id=company.id, export_path=export_path):
                skipped += 1
                print(f"  skipped  {company.name:16} sources={len(sources)}")
                continue

            run = Run(
                company_id=company.id,
                status=RunStatus.SUCCEEDED,
                stage="succeeded",
                progress=100,
                settings_snapshot={
                    "imported": True,
                    "source": "competitive-intel",
                    "intel_db": str(intel_db),
                },
                export_path=export_path,
                started_at=utc_now(),
                finished_at=utc_now(),
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            runs_repo.replace_run_sources(session, run.id, sources)
            runs_repo.append_run_event(
                session,
                run_id=run.id,
                stage="imported",
                message=f"Imported {len(sources)} competitive-intel items",
                payload={"source_count": len(sources), "export_path": export_path},
            )
            imported += 1
            print(f"  imported {company.name:16} sources={len(sources)} run={run.id[:8]}")

    print(f"done imported={imported} skipped={skipped}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import competitive-intel intel.db into Vestige")
    parser.add_argument(
        "--intel-db",
        type=Path,
        default=Path(os.getenv("COMPETITIVE_INTEL_DB", DEFAULT_INTEL_DB)),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return import_intel(args.intel_db.resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
