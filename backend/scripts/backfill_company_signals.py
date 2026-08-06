"""Backfill company_signals from historic signal / competitive-intel runs.

Usage (repo root):
  make backfill-signals
  PYTHONPATH=backend python3 -m scripts.backfill_company_signals
  PYTHONPATH=backend python3 -m scripts.backfill_company_signals --company-id <uuid>
"""

from __future__ import annotations

import argparse
import os

from application.company_signals import (
    backfill_all_companies,
    backfill_company_from_runs,
)
from database import Database


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill company_signals from signal runs"
    )
    parser.add_argument("--company-id", default=None)
    args = parser.parse_args(argv)

    database = Database(_database_url())
    database.create_all()

    with database.session_factory() as session:
        if args.company_id:
            stats = backfill_company_from_runs(session, args.company_id)
            from application.company_activity import refresh_company_activity

            refresh_company_activity(session, args.company_id)
            print(f"company={args.company_id} {stats}")
        else:
            stats = backfill_all_companies(session)
            print(f"done {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
