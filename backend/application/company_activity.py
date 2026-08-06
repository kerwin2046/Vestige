"""Materialized company activity for directory (write-time upsert, read-time cheap)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Company, CompanySignal, Run, RunStatus, utc_now
from repositories.signals import _as_utc


def _start_of_utc_day(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def effective_signals_today(company: Company, *, now: datetime | None = None) -> int:
    """Hide stale day counters after UTC midnight without a rewrite job."""
    last = _as_utc(company.last_signal_at)
    if last is None:
        return 0
    today = _start_of_utc_day(now).date()
    if last.date() < today:
        return 0
    return int(company.signals_today or 0)


def active_24h(company: Company, *, now: datetime | None = None) -> bool:
    last = _as_utc(company.last_signal_at)
    if last is None:
        return False
    current = now or datetime.now(timezone.utc)
    return (current - last).total_seconds() <= 24 * 3600


def activity_dict(company: Company) -> dict:
    last_signal = company.last_signal_at
    last_run = company.last_run_at
    return {
        "signal_count": int(company.signal_count or 0),
        "signals_today": effective_signals_today(company),
        "last_signal_at": last_signal.isoformat()
        if hasattr(last_signal, "isoformat")
        else last_signal,
        "last_run_status": company.last_run_status,
        "last_run_at": last_run.isoformat()
        if hasattr(last_run, "isoformat")
        else last_run,
        "active_24h": active_24h(company),
    }


def refresh_company_activity(session: Session, company_id: str) -> Company | None:
    company = session.get(Company, company_id)
    if company is None:
        return None

    today = _start_of_utc_day().replace(tzinfo=None)
    signal_count = int(
        session.scalar(
            select(func.count())
            .select_from(CompanySignal)
            .where(CompanySignal.company_id == company_id)
        )
        or 0
    )
    signals_today = int(
        session.scalar(
            select(func.count())
            .select_from(CompanySignal)
            .where(
                CompanySignal.company_id == company_id,
                CompanySignal.last_seen_at >= today,
            )
        )
        or 0
    )
    last_signal_at = session.scalar(
        select(func.max(CompanySignal.last_seen_at)).where(
            CompanySignal.company_id == company_id
        )
    )

    latest_run = session.scalar(
        select(Run)
        .where(Run.company_id == company_id)
        .order_by(Run.created_at.desc())
        .limit(1)
    )

    company.signal_count = signal_count
    company.signals_today = signals_today
    company.last_signal_at = last_signal_at
    if latest_run is not None:
        status = latest_run.status
        company.last_run_status = (
            status.value if isinstance(status, RunStatus) else str(status)
        )
        company.last_run_at = latest_run.finished_at or latest_run.created_at
    else:
        company.last_run_status = None
        company.last_run_at = None
    company.activity_updated_at = utc_now()
    session.commit()
    session.refresh(company)
    return company


def refresh_all_company_activity(session: Session) -> dict[str, int]:
    ids = list(session.scalars(select(Company.id)))
    for company_id in ids:
        refresh_company_activity(session, company_id)
    return {"companies": len(ids)}


def activity_revision(session: Session) -> dict:
    """Cheap fingerprint for clients: only refetch lists when this changes."""
    max_signal = session.scalar(select(func.max(CompanySignal.last_seen_at)))
    max_activity = session.scalar(select(func.max(Company.activity_updated_at)))
    total = int(session.scalar(select(func.count()).select_from(CompanySignal)) or 0)

    parts: list[str] = []
    for value in (max_signal, max_activity):
        if value is None:
            continue
        parts.append(value.isoformat() if hasattr(value, "isoformat") else str(value))
    revision = "|".join(parts) if parts else "0"
    return {
        "revision": revision,
        "signal_count": total,
        "max_last_signal_at": max_signal.isoformat()
        if hasattr(max_signal, "isoformat")
        else max_signal,
    }
