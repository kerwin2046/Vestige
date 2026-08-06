"""Seed Manufacturing Social Pulse stream and migrate 「通用」company signals.

Usage (repo root):
  make migrate-mfg-stream
  PYTHONPATH=backend python3 -m scripts.migrate_generic_to_stream --dry-run
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import select

from database import Database
from models import Company, CompanySignal
from repositories import stream_signals as streams_repo


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def migrate(*, dry_run: bool = False) -> dict:
    database = Database(_database_url())
    database.create_all()
    stats = {
        "stream_id": None,
        "stream_slug": "mfg-social",
        "copied": 0,
        "skipped_existing": 0,
        "hidden_companies": 0,
        "dry_run": dry_run,
    }
    try:
        with database.session_factory() as session:
            stream = streams_repo.ensure_mfg_social_stream(session)
            stats["stream_id"] = stream.id

            dump = session.scalar(select(Company).where(Company.name == "通用"))
            if dump is None:
                print("no company named 通用 — stream seeded only")
            else:
                signals = list(
                    session.scalars(
                        select(CompanySignal).where(CompanySignal.company_id == dump.id)
                    )
                )
                for sig in signals:
                    existing = streams_repo.get_by_canonical_url(
                        session, stream.id, sig.canonical_url
                    )
                    if existing is not None:
                        stats["skipped_existing"] += 1
                        continue
                    if dry_run:
                        stats["copied"] += 1
                        continue
                    streams_repo.upsert_stream_signal(
                        session,
                        stream_id=stream.id,
                        url=sig.url,
                        canonical_url=sig.canonical_url,
                        domain=sig.domain or "",
                        source_type=sig.source_type or "social",
                        ownership=sig.ownership or "unknown",
                        confidence=float(sig.confidence or 0),
                        title=sig.title or "",
                        snippet=sig.snippet or "",
                        discovery_path=sig.discovery_path or "migrated:通用",
                        collector=sig.collector or "migrate:generic",
                        detail={
                            **(sig.detail or {}),
                            "migrated_from_company_id": dump.id,
                            "migrated_from": "通用",
                        },
                        seen_at=sig.last_seen_at or sig.first_seen_at,
                    )
                    stats["copied"] += 1

                if not dry_run:
                    dump.directory_hidden = 1
                    dump.updated_at = dump.updated_at  # touch
                    session.commit()
                    streams_repo.refresh_stream_activity(session, stream.id)
                    stats["hidden_companies"] = 1
                else:
                    stats["hidden_companies"] = 1

            if not dry_run:
                # Ensure any previously hidden dumps stay filtered
                for company in streams_repo.find_dump_companies(session):
                    if not company.directory_hidden:
                        company.directory_hidden = 1
                session.commit()
    finally:
        database.dispose()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed mfg-social stream and migrate 通用 signals"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = migrate(dry_run=args.dry_run)
    print(
        f"stream={result['stream_slug']} id={result['stream_id']} "
        f"copied={result['copied']} skipped={result['skipped_existing']} "
        f"hidden={result['hidden_companies']} dry_run={result['dry_run']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
