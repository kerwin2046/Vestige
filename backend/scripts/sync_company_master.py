"""Bidirectional company master sync: Vestige ↔ MfgRadar.

Match key: normalized website domain (fallback: casefold name).
- Creates missing companies on both sides.
- Never renames existing MfgRadar competitors (intel_entries keyed by name).
- On Vestige: fills empty domain/industry; adds the other side's display name as alias.
- Updates ~/.mfgradar/config.json competitors list to match SQLite.

Usage (repo root, venv active):
  make sync-companies
  PYTHONPATH=backend python3 -m scripts.sync_company_master --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select

from database import Database
from models import Company, utc_now


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _vestige_db_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def _mfgradar_home() -> Path:
    return Path(os.getenv("MFGRADAR_HOME", Path.home() / ".mfgradar"))


def _mfgradar_db_path() -> Path:
    return Path(os.getenv("MFGRADAR_DATABASE", _mfgradar_home() / "mfgradar.sqlite"))


def _mfgradar_config_path() -> Path:
    return _mfgradar_home() / "config.json"


def normalize_domain(value: str | None) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = f"//{value}"
    host = urlsplit(value).hostname or ""
    return host.removeprefix("www.")


def website_from_domain(domain: str) -> str:
    domain = normalize_domain(domain)
    return f"https://www.{domain}/" if domain else ""


@dataclass
class MasterCompany:
    name: str
    domain: str = ""
    website: str = ""
    industry: str = ""
    location: str = ""
    aliases: list[str] = field(default_factory=list)
    enabled: bool = True
    vestige_id: str | None = None
    mf_name: str | None = None  # existing MfgRadar competitor name (do not rename)


def load_mfgradar() -> list[MasterCompany]:
    db_path = _mfgradar_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"MfgRadar DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT name, website, enabled FROM competitors ORDER BY name COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()

    companies: list[MasterCompany] = []
    for row in rows:
        domain = normalize_domain(row["website"])
        companies.append(
            MasterCompany(
                name=row["name"],
                domain=domain,
                website=row["website"] or website_from_domain(domain),
                enabled=bool(row["enabled"]),
                mf_name=row["name"],
            )
        )
    return companies


def load_vestige(session) -> list[MasterCompany]:
    companies: list[MasterCompany] = []
    for row in session.scalars(select(Company).order_by(Company.name.asc())):
        companies.append(
            MasterCompany(
                name=row.name,
                domain=normalize_domain(row.official_domain),
                website=website_from_domain(row.official_domain),
                industry=row.industry or "",
                location=row.location or "",
                aliases=list(row.aliases or []),
                vestige_id=row.id,
            )
        )
    return companies


def merge_masters(
    vestige: list[MasterCompany], mfgradar: list[MasterCompany]
) -> list[MasterCompany]:
    """Union by domain, then by casefold name."""
    merged: list[MasterCompany] = []
    by_domain: dict[str, MasterCompany] = {}
    by_name: dict[str, MasterCompany] = {}

    def remember(item: MasterCompany) -> None:
        merged.append(item)
        if item.domain:
            by_domain[item.domain] = item
        by_name[item.name.casefold()] = item
        for alias in item.aliases:
            by_name[alias.casefold()] = item

    def attach_alias(item: MasterCompany, alias: str) -> None:
        alias = alias.strip()
        if not alias:
            return
        if alias.casefold() == item.name.casefold():
            return
        if alias.casefold() in {a.casefold() for a in item.aliases}:
            return
        item.aliases.append(alias)

    for item in vestige:
        remember(
            MasterCompany(
                name=item.name,
                domain=item.domain,
                website=item.website,
                industry=item.industry,
                location=item.location,
                aliases=list(item.aliases),
                vestige_id=item.vestige_id,
            )
        )

    for item in mfgradar:
        hit = None
        if item.domain and item.domain in by_domain:
            hit = by_domain[item.domain]
        elif item.name.casefold() in by_name:
            hit = by_name[item.name.casefold()]

        if hit is None:
            remember(
                MasterCompany(
                    name=item.name,
                    domain=item.domain,
                    website=item.website or website_from_domain(item.domain),
                    enabled=item.enabled,
                    mf_name=item.mf_name,
                )
            )
            continue

        # Prefer MfgRadar display casing when Vestige name is a lowercase slug.
        if hit.name.islower() and not item.name.islower():
            attach_alias(hit, hit.name)
            hit.name = item.name
        else:
            attach_alias(hit, item.name)

        if item.domain and not hit.domain:
            hit.domain = item.domain
            hit.website = item.website or website_from_domain(item.domain)
            by_domain[hit.domain] = hit
        hit.mf_name = item.mf_name
        hit.enabled = item.enabled
        by_name[item.name.casefold()] = hit

    return merged


def apply_vestige(session, masters: list[MasterCompany], *, dry_run: bool) -> dict:
    existing = {c.id: c for c in session.scalars(select(Company))}
    by_domain = {
        normalize_domain(c.official_domain): c
        for c in existing.values()
        if c.official_domain
    }
    by_name = {c.name.casefold(): c for c in existing.values()}

    created = updated = 0
    for master in masters:
        row = None
        if master.vestige_id and master.vestige_id in existing:
            row = existing[master.vestige_id]
        elif master.domain and master.domain in by_domain:
            row = by_domain[master.domain]
        elif master.name.casefold() in by_name:
            row = by_name[master.name.casefold()]

        if row is None:
            created += 1
            if dry_run:
                print(f"  [vestige+] {master.name} ({master.domain})")
                continue
            row = Company(
                id=str(uuid4()),
                name=master.name,
                official_domain=master.domain,
                industry=master.industry,
                location=master.location,
                aliases=list(master.aliases),
            )
            session.add(row)
            session.flush()
            existing[row.id] = row
            if row.official_domain:
                by_domain[row.official_domain] = row
            by_name[row.name.casefold()] = row
            continue

        changed = False
        # Keep Vestige id; enrich fields. Prefer nicer display name if currently slug-like.
        if row.name.islower() and not master.name.islower() and row.name.casefold() == master.name.casefold():
            row.name = master.name
            changed = True
        elif master.name.casefold() != row.name.casefold():
            aliases = list(row.aliases or [])
            if master.name.casefold() not in {a.casefold() for a in aliases} and master.name.casefold() != row.name.casefold():
                aliases.append(master.name)
                row.aliases = aliases
                changed = True

        for alias in master.aliases:
            aliases = list(row.aliases or [])
            if alias.casefold() not in {a.casefold() for a in aliases} and alias.casefold() != row.name.casefold():
                aliases.append(alias)
                row.aliases = aliases
                changed = True

        if master.domain and not row.official_domain:
            row.official_domain = master.domain
            changed = True
        if master.industry and not row.industry:
            row.industry = master.industry
            changed = True
        if master.location and not row.location:
            row.location = master.location
            changed = True

        if changed:
            updated += 1
            row.updated_at = utc_now()
            if dry_run:
                print(f"  [vestige~] {row.name} ({row.official_domain})")

    if not dry_run:
        session.commit()
    return {"created": created, "updated": updated}


def apply_mfgradar(masters: list[MasterCompany], *, dry_run: bool) -> dict:
    db_path = _mfgradar_db_path()
    config_path = _mfgradar_config_path()
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        existing = {
            normalize_domain(row["website"]): row["name"]
            for row in conn.execute("SELECT name, website FROM competitors")
            if normalize_domain(row["website"])
        }
        existing_names = {
            row["name"].casefold(): row["name"]
            for row in conn.execute("SELECT name FROM competitors")
        }

        created = updated = 0
        desired: list[dict] = []

        for master in masters:
            domain = master.domain
            website = master.website or website_from_domain(domain)
            # Preserve existing MfgRadar name when matched (intel FK).
            if master.mf_name:
                name = master.mf_name
            elif domain and domain in existing:
                name = existing[domain]
            elif master.name.casefold() in existing_names:
                name = existing_names[master.name.casefold()]
            else:
                name = master.name

            desired.append(
                {
                    "name": name,
                    "website": website,
                    "enabled": master.enabled if master.mf_name is not None else True,
                }
            )

            if name.casefold() in existing_names:
                # Update website if empty / mismatched domain
                row = conn.execute(
                    "SELECT website FROM competitors WHERE name = ? COLLATE NOCASE",
                    (name,),
                ).fetchone()
                current_domain = normalize_domain(row["website"] if row else "")
                if domain and current_domain != domain:
                    updated += 1
                    if dry_run:
                        print(f"  [mfgradar~] {name} -> {website}")
                    else:
                        conn.execute(
                            "UPDATE competitors SET website = ?, updated_at = ? WHERE name = ? COLLATE NOCASE",
                            (website, now, name),
                        )
                continue

            created += 1
            if dry_run:
                print(f"  [mfgradar+] {name} ({domain})")
            else:
                conn.execute(
                    """
                    INSERT INTO competitors (name, website, enabled, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                    """,
                    (name, website, now, now),
                )

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    # Keep config.json competitors in sync with desired union (by name).
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}

    # Dedupe desired by casefold name, prefer mf names already chosen.
    uniq: dict[str, dict] = {}
    for item in desired:
        uniq[item["name"].casefold()] = item
    competitors = sorted(uniq.values(), key=lambda x: x["name"].casefold())

    if dry_run:
        print(f"  [config] would write {len(competitors)} competitors -> {config_path}")
    else:
        config["competitors"] = competitors
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"created": created, "updated": updated, "config_competitors": len(competitors)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Vestige ↔ MfgRadar company master data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    print(f"vestige_db={_vestige_db_url()}")
    print(f"mfgradar_db={_mfgradar_db_path()}")
    print(f"mfgradar_config={_mfgradar_config_path()}")
    print(f"dry_run={args.dry_run}")

    mf = load_mfgradar()
    database = Database(_vestige_db_url())
    database.create_all()

    with database.session_factory() as session:
        ve = load_vestige(session)
        masters = merge_masters(ve, mf)
        print(f"merged_master_count={len(masters)} (vestige={len(ve)} mfgradar={len(mf)})")
        print("apply vestige:")
        vstats = apply_vestige(session, masters, dry_run=args.dry_run)
        print(f"  created={vstats['created']} updated={vstats['updated']}")

    print("apply mfgradar:")
    mstats = apply_mfgradar(masters, dry_run=args.dry_run)
    print(
        f"  created={mstats['created']} updated={mstats['updated']} "
        f"config_competitors={mstats['config_competitors']}"
    )
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
