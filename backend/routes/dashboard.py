from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from application.pulse_feed import build_pulse_feed
from database import get_session
from models import Company, CompanySignal, Run, RunSource, RunStatus
from repositories import runs
from repositories import signals as signals_repo
from responses import success
from routes.runs import _serialize
from schemas import CompanyRead, CompanySignalRead

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _start_of_utc_day(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _serialize_feed_item(
    row: CompanySignal,
    *,
    score: float | None = None,
    priority: str | None = None,
) -> dict:
    payload = CompanySignalRead.model_validate(row).model_dump(mode="json")
    company = getattr(row, "company", None)
    payload["company"] = (
        CompanyRead.model_validate(company).model_dump(mode="json") if company else None
    )
    if score is not None:
        payload["score"] = score
    if priority is not None:
        payload["priority"] = priority
    return payload


def _serialize_pulse(pulse: dict) -> dict:
    return {
        "window": pulse["window"],
        "window_label": pulse["window_label"],
        "must_see": [
            _serialize_feed_item(item["row"], score=item["score"], priority=item["priority"])
            for item in pulse["must_see"]
        ],
        "feed": [
            _serialize_feed_item(item["row"], score=item["score"], priority=item["priority"])
            for item in pulse["feed"]
        ],
        "feed_total": pulse["feed_total"],
        "offset": pulse["offset"],
        "limit": pulse["limit"],
        "has_more": pulse["has_more"],
        "next_offset": pulse["next_offset"],
        "candidate_count": pulse["candidate_count"],
    }


def _fill_series_days(
    rows: list[tuple[str, int, int, int]], *, days: int = 7
) -> list[dict]:
    today = _start_of_utc_day().date()
    by_day = {day: (high, medium, low) for day, high, medium, low in rows}
    series: list[dict] = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        high, medium, low = by_day.get(day, (0, 0, 0))
        series.append(
            {
                "day": day,
                "high": high,
                "medium": medium,
                "low": low,
                "total": high + medium + low,
            }
        )
    return series


@router.get("")
def dashboard(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    company_count = session.scalar(select(func.count()).select_from(Company)) or 0
    run_count = session.scalar(select(func.count()).select_from(Run)) or 0
    queued_count = (
        session.scalar(
            select(func.count())
            .select_from(Run)
            .where(Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]))
        )
        or 0
    )
    source_count = session.scalar(select(func.count()).select_from(RunSource)) or 0
    signal_count = signals_repo.count_all_signals(session)
    signals_today = signals_repo.count_signals_since(session, _start_of_utc_day())

    since_7d = _start_of_utc_day() - timedelta(days=6)
    series_rows = signals_repo.signals_by_day_since(session, since_7d)
    signal_series = _fill_series_days(series_rows, days=7)
    type_rows = signals_repo.signal_type_breakdown(session, limit=6)
    type_total = sum(count for _, count in type_rows) or 1
    top_signal_types = [
        {
            "key": key,
            "count": count,
            "share": round(count / type_total, 4),
        }
        for key, count in type_rows
    ]

    pulse = _serialize_pulse(
        build_pulse_feed(session, limit=limit, offset=offset, pin_limit=6, min_fill=12)
    )
    recent_runs = runs.list_runs(session)[:8]
    recent_insights = pulse["must_see"][:6] or pulse["feed"][:6]

    return success(
        {
            "company_count": company_count,
            "run_count": run_count,
            "queued_count": queued_count,
            "source_count": source_count,
            "signal_count": signal_count,
            "signals_today": signals_today,
            "signal_series": signal_series,
            "top_signal_types": top_signal_types,
            "pulse": pulse,
            # Back-compat aliases used by older clients
            "recent_signals": pulse["must_see"] + pulse["feed"],
            "recent_insights": recent_insights,
            "recent_runs": [
                _serialize(run, include_company=True) for run in recent_runs
            ],
        }
    )


@router.get("/feed")
def dashboard_feed(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """Paginated ranked pulse feed (Load more)."""
    pulse = _serialize_pulse(
        build_pulse_feed(session, limit=limit, offset=offset, pin_limit=6, min_fill=12)
    )
    return success(pulse)
