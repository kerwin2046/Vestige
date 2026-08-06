"""CLI: dispatch shared OpenClaw signals collector across a company queue.

Usage (repo root):
  make dispatch-signals
  make dispatch-signals LIMIT=10 TIER=target
  make dispatch-signals LIMIT=5 TIER=monitoring WAIT=1 LOCAL=1
"""

from __future__ import annotations

import argparse
import os

from application.signals_collector import dispatch_signals, scaffold_signals_collector
from database import Database


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch shared signals collector")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--tier", default="monitoring")
    parser.add_argument("--role", default=None)
    parser.add_argument("--all-fresh", action="store_true", help="Include non-stale too")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--scaffold-only", action="store_true")
    args = parser.parse_args(argv)

    if args.scaffold_only:
        path = scaffold_signals_collector()
        print(f"scaffolded {path}")
        return 0

    database = Database(_database_url())
    database.create_all()
    with database.session_factory() as session:
        result = dispatch_signals(
            session,
            limit=args.limit,
            tier=None if args.tier in {"", "all", "*"} else args.tier,
            role=args.role,
            stale_only=not args.all_fresh,
            wait=args.wait,
            local=args.local,
            timeout_seconds=args.timeout,
        )

    print(
        f"dispatched mode={result['mode']} tier={result['tier']} "
        f"queued={result['queued']} started={result['started']} failed={result['failed']}"
    )
    for item in result["results"]:
        print(
            f"  {item['status']:8} {item['company_name'][:24]:24} "
            f"pid={item.get('pid')} log={item['log_path']}"
        )
    for err in result["errors"]:
        print(f"  FAILED   {err['company_name']}: {err['error']}")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
