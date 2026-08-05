"""Import B2B Platform Radar DB into Vestige channels table.

Maps:
  discovered_platforms (valid B2B) + golden_samples → kind=platform
  associations → kind=association

Usage (repo root):
  make import-b2b
  PYTHONPATH=backend python3 -m scripts.import_b2b_db --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from database import Database
from models import Channel, utc_now

DEFAULT_B2B_DB = Path(
    "/home/chenyibwgmail.com/桌面/Projects/CHENYI/B2B/backend/data/b2b_platforms.db"
)


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def _host_of(url: str | None) -> str:
    if not url:
        return ""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def _normalize_domain(domain: str | None, url: str | None = None) -> str:
    domain = (domain or "").strip().lower().removeprefix("www.")
    if domain:
        return domain
    return _host_of(url)


def _as_dict_detail(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None and v != ""}


def load_platforms(conn: sqlite3.Connection) -> list[dict]:
    rows: list[dict] = []

    # High-quality discovered platforms
    try:
        cur = conn.execute(
            """
            SELECT platform_name, url, domain, platform_type, source,
                   search_keyword, ai_score, ai_analysis, status,
                   has_free_registration, registration_url, is_valid_b2b
            FROM discovered_platforms
            WHERE is_valid_b2b = 1 OR COALESCE(ai_score, 0) >= 0.7
            """
        )
        for row in cur.fetchall():
            rows.append(
                {
                    "kind": "platform",
                    "name": (row["platform_name"] or row["domain"] or "Unknown").strip(),
                    "url": (row["url"] or "").strip(),
                    "domain": _normalize_domain(row["domain"], row["url"]),
                    "industry": "",
                    "country": "",
                    "channel_type": (row["platform_type"] or "").strip(),
                    "score": float(row["ai_score"] or 0),
                    "status": (row["status"] or "active").strip() or "active",
                    "source": "b2b-radar",
                    "has_member_directory": 0,
                    "detail": _as_dict_detail(
                        origin="discovered_platforms",
                        search_keyword=row["search_keyword"],
                        source=row["source"],
                        ai_analysis=row["ai_analysis"],
                        has_free_registration=row["has_free_registration"],
                        registration_url=row["registration_url"],
                        is_valid_b2b=row["is_valid_b2b"],
                    ),
                }
            )
    except sqlite3.Error as exc:
        print(f"skip discovered_platforms: {exc}")

    # Golden samples as high-trust platform seeds
    try:
        cur = conn.execute(
            """
            SELECT platform_name, url, domain, industry, country,
                   features, keywords, analysis_result
            FROM golden_samples
            """
        )
        for row in cur.fetchall():
            rows.append(
                {
                    "kind": "platform",
                    "name": (row["platform_name"] or row["domain"] or "Unknown").strip(),
                    "url": (row["url"] or "").strip(),
                    "domain": _normalize_domain(row["domain"], row["url"]),
                    "industry": (row["industry"] or "").strip(),
                    "country": (row["country"] or "").strip(),
                    "channel_type": "golden_sample",
                    "score": 1.0,
                    "status": "active",
                    "source": "b2b-radar",
                    "has_member_directory": 0,
                    "detail": _as_dict_detail(
                        origin="golden_samples",
                        features=row["features"],
                        keywords=row["keywords"],
                        analysis_result=row["analysis_result"],
                    ),
                }
            )
    except sqlite3.Error as exc:
        print(f"skip golden_samples: {exc}")

    return rows


def load_associations(conn: sqlite3.Connection) -> list[dict]:
    rows: list[dict] = []
    try:
        cur = conn.execute(
            """
            SELECT name, full_name, url, domain, country, industry,
                   description, has_member_directory, member_url,
                   source, search_keyword, ai_score, ai_analysis, status
            FROM associations
            WHERE COALESCE(status, '') NOT IN ('rejected', 'deleted')
            """
        )
        for row in cur.fetchall():
            name = (row["name"] or row["full_name"] or row["domain"] or "Unknown").strip()
            if name in {"无法确定", "Unknown", ""}:
                continue
            rows.append(
                {
                    "kind": "association",
                    "name": name,
                    "url": (row["url"] or "").strip(),
                    "domain": _normalize_domain(row["domain"], row["url"]),
                    "industry": (row["industry"] or "").strip(),
                    "country": (row["country"] or "").strip(),
                    "channel_type": "association",
                    "score": float(row["ai_score"] or 0),
                    "status": (row["status"] or "active").strip() or "active",
                    "source": "b2b-radar",
                    "has_member_directory": int(row["has_member_directory"] or 0),
                    "detail": _as_dict_detail(
                        origin="associations",
                        full_name=row["full_name"],
                        description=row["description"],
                        member_url=row["member_url"],
                        search_keyword=row["search_keyword"],
                        association_source=row["source"],
                        ai_analysis=row["ai_analysis"],
                    ),
                }
            )
    except sqlite3.Error as exc:
        print(f"skip associations: {exc}")
    return rows


def upsert_channel(session, payload: dict, *, dry_run: bool) -> str:
    domain = payload["domain"]
    kind = payload["kind"]
    if not domain:
        return "skip"

    existing = session.scalar(
        select(Channel).where(Channel.kind == kind, Channel.domain == domain)
    )
    if existing:
        # Prefer higher score / richer metadata
        changed = False
        if payload["score"] > (existing.score or 0):
            existing.score = payload["score"]
            changed = True
        if payload["name"] and (
            not existing.name or existing.name in {"Unknown", "无法确定"}
        ):
            existing.name = payload["name"]
            changed = True
        if payload["industry"] and not existing.industry:
            existing.industry = payload["industry"]
            changed = True
        if payload["country"] and not existing.country:
            existing.country = payload["country"]
            changed = True
        if payload["channel_type"] and (
            not existing.channel_type or existing.channel_type == "golden_sample"
        ):
            if payload["channel_type"] != "golden_sample" or not existing.channel_type:
                existing.channel_type = payload["channel_type"]
                changed = True
        if payload["has_member_directory"] and not existing.has_member_directory:
            existing.has_member_directory = payload["has_member_directory"]
            changed = True
        if payload["url"] and not existing.url:
            existing.url = payload["url"]
            changed = True
        if payload.get("detail"):
            merged = dict(existing.detail or {})
            merged.update(payload["detail"])
            existing.detail = merged
            changed = True
        if changed:
            existing.updated_at = utc_now()
            return "updated"
        return "unchanged"

    if dry_run:
        return "would_create"

    session.add(
        Channel(
            kind=kind,
            name=payload["name"],
            url=payload["url"],
            domain=domain,
            industry=payload["industry"],
            country=payload["country"],
            channel_type=payload["channel_type"],
            score=payload["score"],
            status=payload["status"],
            source=payload["source"],
            has_member_directory=payload["has_member_directory"],
            detail=payload.get("detail"),
        )
    )
    return "created"


def run_import(b2b_db: Path, *, dry_run: bool = False) -> dict:
    if not b2b_db.exists():
        raise FileNotFoundError(f"B2B db not found: {b2b_db}")

    conn = sqlite3.connect(b2b_db)
    conn.row_factory = sqlite3.Row
    try:
        payloads = load_platforms(conn) + load_associations(conn)
    finally:
        conn.close()

    database = Database(_database_url())
    database.create_all()
    stats = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skip": 0,
        "would_create": 0,
        "platforms": 0,
        "associations": 0,
    }

    with database.session_factory() as session:
        for payload in payloads:
            if payload["kind"] == "platform":
                stats["platforms"] += 1
            else:
                stats["associations"] += 1
            result = upsert_channel(session, payload, dry_run=dry_run)
            stats[result] = stats.get(result, 0) + 1
        if not dry_run:
            session.commit()

    database.dispose()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import B2B Radar DB into Vestige channels")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.getenv("B2B_PLATFORMS_DB", str(DEFAULT_B2B_DB))),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stats = run_import(args.db, dry_run=args.dry_run)
    print(json.dumps({"db": str(args.db), "dry_run": args.dry_run, **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
