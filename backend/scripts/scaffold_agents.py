"""Scaffold OpenClaw agent dirs for all Vestige companies."""

from __future__ import annotations

from sqlalchemy import select

from application.scaffold_agent import agents_root, scaffold_company_agent
from database import Database
from models import Company
from scripts.sync_company_master import _vestige_db_url


def main() -> int:
    database = Database(_vestige_db_url())
    database.create_all()
    root = agents_root()
    print(f"agents_root={root}")
    with database.session_factory() as session:
        companies = list(session.scalars(select(Company).order_by(Company.name.asc())))
        for company in companies:
            path = scaffold_company_agent(company)
            print(f"  {company.name} -> {path}")
    print(f"done count={len(companies)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
