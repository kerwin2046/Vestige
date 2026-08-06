from __future__ import annotations

import argparse
import asyncio
import os
import traceback
from pathlib import Path

from application.merge_sources import (
    latest_successful_footprint_run,
    merge_footprint_sources,
    source_to_dict,
)
from application.orchestrate import DiscoveryEmptyError, orchestrate_run
from database import Database
from models import RunStatus
from repositories import runs as runs_repo


def _database_url() -> str:
    return os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")


def _run_output_dir(run_id: str) -> str:
    path = Path("output") / "runs" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


async def process_run(database: Database, run_id: str) -> None:
    with database.session_factory() as session:
        run = runs_repo.get_run(session, run_id)
        if run is None:
            return
        if run.status == RunStatus.CANCEL_REQUESTED:
            runs_repo.mark_run_cancelled(session, run)
            return

        company = run.company
        company_payload = {
            "name": company.name,
            "official_domain": company.official_domain,
            "industry": company.industry,
            "location": company.location,
            "aliases": list(company.aliases or []),
        }
        settings = dict(run.settings_snapshot or {})
        runs_repo.append_run_event(
            session,
            run_id=run.id,
            stage="starting",
            message=f"Claimed run for {company.name}",
            payload={"lanes": settings.get("lanes") or ["footprint", "channels", "owned"]},
        )
        runs_repo.update_run_progress(session, run, stage="discovering", progress=10)

    try:
        with database.session_factory() as session:
            outcome = await orchestrate_run(
                session,
                company=company_payload,
                settings=settings,
                output_dir=_run_output_dir(run_id),
            )
    except DiscoveryEmptyError as exc:
        with database.session_factory() as session:
            run = runs_repo.get_run(session, run_id)
            if run is None:
                return
            if run.status == RunStatus.CANCEL_REQUESTED:
                runs_repo.mark_run_cancelled(session, run)
                return
            lanes = exc.lanes or {}
            sources = exc.sources or []
            snap = dict(run.settings_snapshot or {})
            snap["lane_results"] = lanes
            snap["warning"] = str(exc)
            run.settings_snapshot = snap
            session.commit()
            if sources:
                runs_repo.replace_run_sources(session, run.id, sources)
            for lane_name, lane_info in lanes.items():
                runs_repo.append_run_event(
                    session,
                    run_id=run.id,
                    stage=f"lane:{lane_name}",
                    level="warning",
                    message=(
                        f"Lane {lane_name}: {lane_info.get('status')} · "
                        f"{lane_info.get('source_count', 0)} sources"
                        + (f" · {lane_info.get('error')}" if lane_info.get("error") else "")
                    ),
                    payload=lane_info,
                )
            error = f"{type(exc).__name__}: {exc}"
            runs_repo.append_run_event(
                session,
                run_id=run_id,
                stage="failed",
                level="error",
                message=error,
                payload={"lanes": lanes, "source_count": len(sources)},
            )
            runs_repo.mark_run_failed(session, run, error=error)
        return
    except Exception as exc:
        with database.session_factory() as session:
            run = runs_repo.get_run(session, run_id)
            if run is None:
                return
            if run.status == RunStatus.CANCEL_REQUESTED:
                runs_repo.mark_run_cancelled(session, run)
                return
            error = f"{type(exc).__name__}: {exc}"
            runs_repo.append_run_event(
                session,
                run_id=run_id,
                stage="failed",
                level="error",
                message=error,
                payload={"traceback": traceback.format_exc()[-4000:]},
            )
            runs_repo.mark_run_failed(session, run, error=error)
        raise

    with database.session_factory() as session:
        run = runs_repo.get_run(session, run_id)
        if run is None:
            return
        if run.status == RunStatus.CANCEL_REQUESTED:
            runs_repo.mark_run_cancelled(session, run)
            return

        sources = outcome.get("sources") or []
        lanes = outcome.get("lanes") or {}
        warning = outcome.get("warning")
        merge_stats = {
            "added": len(sources),
            "updated": 0,
            "kept": 0,
            "total": len(sources),
            "base": 0,
            "incoming": len(sources),
        }

        previous = latest_successful_footprint_run(
            session, run.company_id, exclude_run_id=run.id
        )
        if previous is not None:
            base = [
                source_to_dict(row)
                for row in runs_repo.list_run_sources(session, previous.id)
            ]
            sources, merge_stats = merge_footprint_sources(base, sources)

        for lane_name, lane_info in lanes.items():
            level = "warning" if lane_info.get("status") in {"empty", "error", "seeded"} else "info"
            runs_repo.append_run_event(
                session,
                run_id=run.id,
                stage=f"lane:{lane_name}",
                level=level,
                message=(
                    f"Lane {lane_name}: {lane_info.get('status')} · "
                    f"{lane_info.get('source_count', 0)} sources"
                    + (f" · {lane_info.get('error')}" if lane_info.get("error") else "")
                ),
                payload=lane_info,
            )

        snap = dict(run.settings_snapshot or {})
        snap["lane_results"] = lanes
        snap["merge"] = merge_stats
        if previous is not None:
            snap["merged_from_run_id"] = previous.id
        if warning:
            snap["warning"] = warning
        run.settings_snapshot = snap
        session.commit()

        runs_repo.update_run_progress(session, run, stage="persisting", progress=90)
        runs_repo.replace_run_sources(session, run.id, sources)
        runs_repo.append_run_event(
            session,
            run_id=run.id,
            stage="persisting",
            message=(
                f"Persisted {merge_stats['total']} sources "
                f"(+{merge_stats['added']} new, ~{merge_stats['updated']} updated, "
                f"{merge_stats['kept']} kept from prior)"
            ),
            payload={
                "source_count": merge_stats["total"],
                "merge": merge_stats,
                "lanes": lanes,
                "warning": warning,
                "merged_from_run_id": previous.id if previous else None,
            },
        )
        runs_repo.mark_run_succeeded(
            session,
            run,
            export_path=outcome.get("export_path"),
        )
        runs_repo.append_run_event(
            session,
            run_id=run.id,
            stage="succeeded",
            level="warning" if warning else "info",
            message=warning or "Run completed successfully",
            payload={"lanes": lanes},
        )
        try:
            from application.company_activity import refresh_company_activity

            refresh_company_activity(session, run.company_id)
        except Exception as exc:  # noqa: BLE001 — activity is best-effort
            print(f"activity refresh failed for {run.company_id[:8]}: {exc}")


async def worker_loop(*, poll_interval: float = 2.0, once: bool = False) -> None:
    database = Database(_database_url())
    database.create_all()
    print(f"Vestige worker started · db={_database_url()}")

    with database.session_factory() as session:
        recovered = runs_repo.recover_orphaned_runs(session)
    if recovered["requeued"] or recovered["cancelled"]:
        print(
            "Recovered orphaned runs · "
            f"requeued={recovered['requeued']} cancelled={recovered['cancelled']}"
        )

    try:
        while True:
            with database.session_factory() as session:
                claimed = runs_repo.claim_next_queued_run(session)

            if claimed is None:
                if once:
                    print("No queued runs.")
                    return
                await asyncio.sleep(poll_interval)
                continue

            print(f"Processing run {claimed.id} · company={claimed.company.name}")
            try:
                await process_run(database, claimed.id)
                print(f"Run {claimed.id} succeeded")
            except Exception as exc:
                print(f"Run {claimed.id} failed: {exc}")

            if once:
                return
    finally:
        database.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Vestige discovery worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued run and exit",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between queue polls when idle",
    )
    args = parser.parse_args(argv)
    asyncio.run(worker_loop(poll_interval=args.poll_interval, once=args.once))


if __name__ == "__main__":
    main()
