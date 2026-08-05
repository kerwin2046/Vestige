from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import Run, RunEvent, RunSource, RunStatus, utc_now


def list_runs(
    session: Session,
    *,
    company_id: str | None = None,
    status: RunStatus | None = None,
) -> list[Run]:
    statement = (
        select(Run)
        .options(selectinload(Run.company))
        .order_by(Run.created_at.desc())
    )
    if company_id:
        statement = statement.where(Run.company_id == company_id)
    if status:
        statement = statement.where(Run.status == status)
    return list(session.scalars(statement))


def get_run(session: Session, run_id: str) -> Run | None:
    statement = (
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.company))
    )
    return session.scalar(statement)


def create_run(
    session: Session,
    *,
    company_id: str,
    settings_snapshot: dict,
    previous_run_id: str | None = None,
) -> Run:
    run = Run(
        company_id=company_id,
        settings_snapshot=settings_snapshot,
        previous_run_id=previous_run_id,
    )
    session.add(run)
    session.commit()
    return get_run(session, run.id)


def latest_successful_run(session: Session, company_id: str) -> Run | None:
    return session.scalar(
        select(Run)
        .where(
            Run.company_id == company_id,
            Run.status == RunStatus.SUCCEEDED,
        )
        .order_by(Run.finished_at.desc(), Run.created_at.desc())
        .limit(1)
    )


def request_cancel(session: Session, run: Run) -> Run:
    run.status = RunStatus.CANCEL_REQUESTED
    run.stage = "cancel_requested"
    session.commit()
    return get_run(session, run.id)


def list_run_sources(session: Session, run_id: str) -> list[RunSource]:
    statement = (
        select(RunSource)
        .where(RunSource.run_id == run_id)
        .order_by(RunSource.confidence.desc(), RunSource.domain.asc())
    )
    return list(session.scalars(statement))


def claim_next_queued_run(session: Session) -> Run | None:
    """Claim the oldest queued run. Suitable for a single local worker process."""
    run = session.scalar(
        select(Run)
        .where(Run.status == RunStatus.QUEUED)
        .order_by(Run.created_at.asc())
        .limit(1)
    )
    if run is None:
        return None
    run.status = RunStatus.RUNNING
    run.stage = "starting"
    run.progress = 1
    run.started_at = utc_now()
    run.error = None
    session.commit()
    return get_run(session, run.id)


def update_run_progress(
    session: Session,
    run: Run,
    *,
    stage: str,
    progress: int,
) -> Run:
    run.stage = stage
    run.progress = max(0, min(100, progress))
    session.commit()
    return get_run(session, run.id)


def append_run_event(
    session: Session,
    *,
    run_id: str,
    message: str,
    stage: str = "",
    level: str = "info",
    payload: dict | None = None,
) -> RunEvent:
    event = RunEvent(
        run_id=run_id,
        level=level,
        stage=stage,
        message=message,
        payload=payload or {},
    )
    session.add(event)
    session.commit()
    return event


def replace_run_sources(session: Session, run_id: str, sources: list[dict]) -> list[RunSource]:
    existing = list(
        session.scalars(select(RunSource).where(RunSource.run_id == run_id))
    )
    for row in existing:
        session.delete(row)
    session.flush()

    created: list[RunSource] = []
    for item in sources:
        row = RunSource(
            run_id=run_id,
            url=item["url"],
            canonical_url=item.get("canonical_url") or item["url"],
            domain=item.get("domain") or "",
            source_type=item.get("source_type") or "other",
            ownership=item.get("ownership") or "unknown",
            confidence=float(item.get("confidence") or 0.0),
            title=item.get("title") or "",
            snippet=item.get("snippet") or "",
            discovery_path=item.get("discovery_path") or "",
            bfs_round=int(item.get("bfs_round") or 0),
            detail=item.get("detail"),
        )
        session.add(row)
        created.append(row)
    session.commit()
    return created


def mark_run_succeeded(
    session: Session,
    run: Run,
    *,
    export_path: str | None,
) -> Run:
    run.status = RunStatus.SUCCEEDED
    run.stage = "succeeded"
    run.progress = 100
    run.export_path = export_path
    run.error = None
    run.finished_at = utc_now()
    session.commit()
    return get_run(session, run.id)


def mark_run_failed(session: Session, run: Run, *, error: str) -> Run:
    run.status = RunStatus.FAILED
    run.stage = "failed"
    run.error = error
    run.finished_at = utc_now()
    session.commit()
    return get_run(session, run.id)


def mark_run_cancelled(session: Session, run: Run) -> Run:
    run.status = RunStatus.CANCELLED
    run.stage = "cancelled"
    run.finished_at = utc_now()
    session.commit()
    return get_run(session, run.id)
