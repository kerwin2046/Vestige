"""CLI: run OpenClaw agent for a Vestige company.

Examples:
  make run-agent DOMAIN=xometry.com
  make run-agent ID=<company-uuid>
  PYTHONPATH=backend python3 -m scripts.run_openclaw_agent --domain xometry.com
  PYTHONPATH=backend python3 -m scripts.run_openclaw_agent --domain xometry.com --detach
  PYTHONPATH=backend python3 -m scripts.run_openclaw_agent --domain xometry.com --local
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from sqlalchemy import select

from application.openclaw_agent import run_company_openclaw_agent
from application.scaffold_agent import company_slug
from database import Database
from models import Company


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def _find_company(session, *, company_id: str | None, domain: str | None, name: str | None, slug: str | None) -> Company:
    if company_id:
        company = session.get(Company, company_id)
        if company is None:
            raise SystemExit(f"company id not found: {company_id}")
        return company

    companies = list(session.scalars(select(Company)))
    if domain:
        key = domain.strip().lower().removeprefix("www.")
        for company in companies:
            d = (company.official_domain or "").strip().lower().removeprefix("www.")
            if d == key or d.endswith("." + key) or key.endswith("." + d):
                return company
        raise SystemExit(f"no company with domain={domain!r}")

    if slug:
        for company in companies:
            if company_slug(company) == slug:
                return company
        raise SystemExit(f"no company with agent slug={slug!r}")

    if name:
        key = name.strip().lower()
        matches = [c for c in companies if key in (c.name or "").lower()]
        if not matches:
            raise SystemExit(f"no company matching name={name!r}")
        if len(matches) > 1:
            preview = ", ".join(f"{c.name} ({c.official_domain})" for c in matches[:8])
            raise SystemExit(f"ambiguous name={name!r}: {preview}")
        return matches[0]

    raise SystemExit("provide --id, --domain, --slug, or --name")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run OpenClaw agent for a Vestige company")
    parser.add_argument("--id", help="Vestige company UUID")
    parser.add_argument("--domain", help="Company official domain")
    parser.add_argument("--slug", help="Agent directory slug")
    parser.add_argument("--name", help="Company name substring")
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Start OpenClaw in background; write last_run.log",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Pass --local to openclaw agent (embedded, no gateway)",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Agent timeout seconds")
    parser.add_argument("--thinking", default=None, help="Thinking level for openclaw")
    parser.add_argument(
        "--agent",
        default=None,
        help="OpenClaw agent id (default: main / OPENCLAW_AGENT_ID)",
    )
    parser.add_argument(
        "--no-scaffold",
        action="store_true",
        help="Do not refresh scaffold files before running",
    )
    args = parser.parse_args(argv)

    database = Database(_database_url())
    database.create_all()
    try:
        with database.session_factory() as session:
            company = _find_company(
                session,
                company_id=args.id,
                domain=args.domain,
                name=args.name,
                slug=args.slug,
            )
            # Detach ORM object for use after session
            session.expunge(company)

        result = run_company_openclaw_agent(
            company,
            wait=not args.detach,
            local=args.local,
            timeout_seconds=args.timeout,
            thinking=args.thinking,
            openclaw_agent=args.agent,
            scaffold=not args.no_scaffold,
        )
    finally:
        database.dispose()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result.get("status") == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
