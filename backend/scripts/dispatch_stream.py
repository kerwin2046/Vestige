"""CLI: dispatch Manufacturing Social Pulse stream agent.

Usage:
  make dispatch-stream
  make dispatch-stream WAIT=1 LOCAL=1
  make dispatch-stream SCAFFOLD_ONLY=1
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from application.stream_agent import run_mfg_social_pulse, scaffold_mfg_social_agent
from database import Database
from repositories import stream_signals as streams_repo


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch mfg-social stream agent")
    parser.add_argument("--scaffold-only", action="store_true")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--thinking", default=None)
    args = parser.parse_args(argv)

    if args.scaffold_only:
        path = scaffold_mfg_social_agent()
        print(f"scaffolded {path}")
        return 0

    database = Database(_database_url())
    database.create_all()
    try:
        with database.session_factory() as session:
            streams_repo.ensure_mfg_social_stream(session)
            result = run_mfg_social_pulse(
                session,
                wait=args.wait,
                local=args.local,
                timeout_seconds=args.timeout,
                thinking=args.thinking,
            )
    finally:
        database.dispose()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
