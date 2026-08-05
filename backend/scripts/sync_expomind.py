"""Import curated ExpoMind companies into Vestige as layered companies.

Rules (option B):
  - competitor_profiles → tier=target, roles=[competitor]
  - lead_analysis Yes (or High priority) → tier=candidate, roles=[prospect]
  - is_manufacturing=是 AND lead≠No (Yes/Maybe) → candidate, roles=[manufacturer]
    (+ prospect if lead=Yes)

Match key: normalized website domain.
Does NOT dump the full exhibition raw pool.

Usage:
  make sync-expomind
  PYTHONPATH=backend python3 -m scripts.sync_expomind --dry-run
  PYTHONPATH=backend python3 -m scripts.sync_expomind --no-manufacturers
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import select

from database import Database
from models import Company, utc_now


def _vestige_db_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def normalize_domain(value: str | None) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    # ExpoMind sometimes stores multi-line websites
    value = value.splitlines()[0].strip()
    if "://" not in value:
        value = f"//{value}"
    host = urlsplit(value).hostname or ""
    return host.removeprefix("www.")


@dataclass
class Incoming:
    name: str
    domain: str
    industry: str = ""
    location: str = ""
    tier: str = "candidate"
    roles: list[str] = field(default_factory=list)
    priority: str = ""
    provenance: dict = field(default_factory=dict)


def _pg_conn():
    return psycopg2.connect(
        host=os.getenv("EXPOMIND_PG_HOST", os.getenv("PG_HOST", "127.0.0.1")),
        port=int(os.getenv("EXPOMIND_PG_PORT", os.getenv("PG_PORT", "5434"))),
        dbname=os.getenv("EXPOMIND_PG_DB", os.getenv("PG_DB", "expomind")),
        user=os.getenv("EXPOMIND_PG_USER", os.getenv("PG_USER", "postgres")),
        password=os.getenv("EXPOMIND_PG_PASSWORD", os.getenv("PG_PASSWORD", "cy200619")),
    )


def load_competitors(conn) -> list[Incoming]:
    rows = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT company_name, website, industry, discovery_status
            FROM competitor_profiles
            """
        )
        for row in cur.fetchall():
            domain = normalize_domain(row.get("website"))
            if not domain:
                continue
            rows.append(
                Incoming(
                    name=(row.get("company_name") or domain).strip(),
                    domain=domain,
                    industry=(row.get("industry") or "").strip(),
                    tier="target",
                    roles=["competitor"],
                    priority="High",
                    provenance={
                        "origin": "expomind.competitor_profiles",
                        "discovery_status": row.get("discovery_status"),
                    },
                )
            )
    return rows


def load_prospects(conn) -> list[Incoming]:
    rows = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (c.id)
                c.name, c.website, c.country, c.industry, c.is_manufacturing,
                l.is_potential_customer, l.priority_level, e.name AS exhibition_name
            FROM lead_analysis_results l
            JOIN companies c ON c.id = l.company_id
            LEFT JOIN exhibitions e ON e.id = l.exhibition_id
            WHERE (
                lower(coalesce(l.is_potential_customer, '')) = 'yes'
                OR lower(coalesce(l.priority_level, '')) = 'high'
            )
            ORDER BY c.id, l.updated_at DESC NULLS LAST
            """
        )
        for row in cur.fetchall():
            domain = normalize_domain(row.get("website"))
            if not domain:
                continue
            roles = ["prospect"]
            if (row.get("is_manufacturing") or "").strip() == "是":
                roles.append("manufacturer")
            rows.append(
                Incoming(
                    name=(row.get("name") or domain).strip(),
                    domain=domain,
                    industry=(row.get("industry") or "").strip(),
                    location=(row.get("country") or "").strip(),
                    tier="candidate",
                    roles=roles,
                    priority=(row.get("priority_level") or "").strip(),
                    provenance={
                        "origin": "expomind.lead_analysis",
                        "is_potential_customer": row.get("is_potential_customer"),
                        "exhibition": row.get("exhibition_name"),
                        "is_manufacturing": row.get("is_manufacturing"),
                    },
                )
            )
    return rows


def load_manufacturers(conn) -> list[Incoming]:
    """Option B: manufacturing=是 and lead ≠ No (Yes/Maybe) → Candidates."""
    rows = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (c.id)
                c.name, c.website, c.country, c.industry, c.is_manufacturing,
                l.is_potential_customer, l.priority_level, e.name AS exhibition_name
            FROM companies c
            JOIN lead_analysis_results l ON l.company_id = c.id
            LEFT JOIN exhibitions e ON e.id = l.exhibition_id
            WHERE c.is_manufacturing = '是'
              AND lower(coalesce(l.is_potential_customer, '')) <> 'no'
              AND coalesce(c.website, '') <> ''
            ORDER BY c.id, l.updated_at DESC NULLS LAST
            """
        )
        for row in cur.fetchall():
            domain = normalize_domain(row.get("website"))
            if not domain:
                continue
            potential = (row.get("is_potential_customer") or "").strip().lower()
            roles = ["manufacturer"]
            if potential == "yes":
                roles.append("prospect")
            rows.append(
                Incoming(
                    name=(row.get("name") or domain).strip(),
                    domain=domain,
                    industry=(row.get("industry") or "").strip(),
                    location=(row.get("country") or "").strip(),
                    tier="candidate",
                    roles=roles,
                    priority=(row.get("priority_level") or "").strip(),
                    provenance={
                        "origin": "expomind.manufacturer_not_no",
                        "is_potential_customer": row.get("is_potential_customer"),
                        "exhibition": row.get("exhibition_name"),
                        "is_manufacturing": row.get("is_manufacturing"),
                    },
                )
            )
    return rows


def merge_roles(existing: list[str] | None, incoming: list[str]) -> list[str]:
    result = list(existing or [])
    for role in incoming:
        if role and role not in result:
            result.append(role)
    return result


def tier_rank(tier: str) -> int:
    return {"candidate": 1, "target": 2, "monitoring": 3}.get(tier or "candidate", 1)


def upsert(session, item: Incoming, *, dry_run: bool) -> str:
    existing = session.scalar(
        select(Company).where(Company.official_domain == item.domain)
    )
    if existing:
        changed = False
        if tier_rank(item.tier) > tier_rank(existing.tier or "candidate"):
            existing.tier = item.tier
            changed = True
        new_roles = merge_roles(existing.roles, item.roles)
        if new_roles != (existing.roles or []):
            existing.roles = new_roles
            changed = True
        if item.industry and not existing.industry:
            existing.industry = item.industry
            changed = True
        if item.location and not existing.location:
            existing.location = item.location
            changed = True
        if item.priority and (
            not existing.priority
            or (item.priority == "High" and existing.priority != "High")
        ):
            existing.priority = item.priority
            changed = True
        if item.name and existing.name != item.name:
            aliases = list(existing.aliases or [])
            if item.name not in aliases and item.name != existing.name:
                aliases.append(item.name)
                existing.aliases = aliases
                changed = True
        prov = dict(existing.provenance or {})
        prov.update(item.provenance)
        prov["sources"] = sorted(
            set((prov.get("sources") or []) + [item.provenance.get("origin", "expomind")])
        )
        if prov != (existing.provenance or {}):
            existing.provenance = prov
            changed = True
        if existing.source == "manual":
            existing.source = "expomind"
            changed = True
        if changed:
            existing.updated_at = utc_now()
            return "updated"
        return "unchanged"

    if dry_run:
        return "would_create"

    session.add(
        Company(
            name=item.name,
            official_domain=item.domain,
            industry=item.industry,
            location=item.location,
            aliases=[],
            tier=item.tier,
            roles=item.roles,
            priority=item.priority,
            source="expomind",
            provenance={
                **item.provenance,
                "sources": [item.provenance.get("origin", "expomind")],
            },
        )
    )
    return "created"


def run_sync(*, include_manufacturers: bool = True, dry_run: bool = False) -> dict:
    conn = _pg_conn()
    try:
        incoming = load_competitors(conn) + load_prospects(conn)
        if include_manufacturers:
            incoming.extend(load_manufacturers(conn))
    finally:
        conn.close()

    # Prefer competitor tier when same domain appears in both lists
    by_domain: dict[str, Incoming] = {}
    for item in incoming:
        prev = by_domain.get(item.domain)
        if prev is None or tier_rank(item.tier) > tier_rank(prev.tier):
            if prev:
                item.roles = merge_roles(prev.roles, item.roles)
                item.provenance = {**prev.provenance, **item.provenance}
            by_domain[item.domain] = item
        else:
            prev.roles = merge_roles(prev.roles, item.roles)
            prev.provenance = {**item.provenance, **prev.provenance}

    database = Database(_vestige_db_url())
    database.create_all()
    stats = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "would_create": 0,
        "incoming": len(by_domain),
        "competitors": sum(1 for x in by_domain.values() if "competitor" in x.roles),
        "prospects": sum(1 for x in by_domain.values() if "prospect" in x.roles),
        "manufacturers": sum(1 for x in by_domain.values() if "manufacturer" in x.roles),
        "include_manufacturers": include_manufacturers,
    }

    with database.session_factory() as session:
        for item in by_domain.values():
            result = upsert(session, item, dry_run=dry_run)
            stats[result] = stats.get(result, 0) + 1
        if not dry_run:
            session.commit()
    database.dispose()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync curated ExpoMind companies into Vestige")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-manufacturers",
        action="store_true",
        help="Skip option B manufacturer batch (manufacturing=是 AND lead≠No)",
    )
    args = parser.parse_args()
    stats = run_sync(
        include_manufacturers=not args.no_manufacturers,
        dry_run=args.dry_run,
    )
    print(json.dumps({"dry_run": args.dry_run, **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
