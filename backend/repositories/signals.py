"""Company-level signal entity repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import CompanySignal, utc_now


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc)
    return value


def list_company_signals(
    session: Session,
    company_id: str,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[CompanySignal]:
    stmt = (
        select(CompanySignal)
        .where(CompanySignal.company_id == company_id)
        .order_by(CompanySignal.last_seen_at.desc(), CompanySignal.id.desc())
        .offset(max(0, offset))
    )
    if limit is not None:
        stmt = stmt.limit(max(1, limit))
    return list(session.scalars(stmt))


def count_company_signals(session: Session, company_id: str) -> int:
    from sqlalchemy import func

    return int(
        session.scalar(
            select(func.count())
            .select_from(CompanySignal)
            .where(CompanySignal.company_id == company_id)
        )
        or 0
    )


def list_recent_signals(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[CompanySignal]:
    stmt = (
        select(CompanySignal)
        .order_by(CompanySignal.last_seen_at.desc(), CompanySignal.id.desc())
        .offset(max(0, offset))
        .limit(max(1, limit))
    )
    return list(session.scalars(stmt))


def count_signals_since(session: Session, since: datetime) -> int:
    from sqlalchemy import func

    return int(
        session.scalar(
            select(func.count())
            .select_from(CompanySignal)
            .where(CompanySignal.last_seen_at >= since)
        )
        or 0
    )


def count_all_signals(session: Session) -> int:
    from sqlalchemy import func

    return int(session.scalar(select(func.count()).select_from(CompanySignal)) or 0)


def signal_type_breakdown(
    session: Session, *, limit: int = 8
) -> list[tuple[str, int]]:
    from sqlalchemy import func

    rows = session.execute(
        select(CompanySignal.source_type, func.count())
        .group_by(CompanySignal.source_type)
        .order_by(func.count().desc())
        .limit(max(1, limit))
    ).all()
    return [(str(name or "other"), int(count)) for name, count in rows]


def signals_by_day_since(
    session: Session, since: datetime
) -> list[tuple[str, int, int, int]]:
    """Return (day_iso, high, medium, low) buckets by confidence."""
    from collections import defaultdict

    rows = session.execute(
        select(CompanySignal.last_seen_at, CompanySignal.confidence).where(
            CompanySignal.last_seen_at >= since
        )
    ).all()
    buckets: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for seen_at, confidence in rows:
        if seen_at is None:
            continue
        day = _as_utc(seen_at)
        if day is None:
            continue
        key = day.date().isoformat()
        conf = float(confidence or 0)
        if conf >= 0.8:
            buckets[key][0] += 1
        elif conf >= 0.5:
            buckets[key][1] += 1
        else:
            buckets[key][2] += 1
    return [
        (day, vals[0], vals[1], vals[2])
        for day, vals in sorted(buckets.items())
    ]


def daily_signal_totals(
    session: Session, since: datetime
) -> list[tuple[str, int]]:
    rows = signals_by_day_since(session, since)
    return [(day, high + medium + low) for day, high, medium, low in rows]


def get_by_canonical_url(
    session: Session, company_id: str, canonical_url: str
) -> CompanySignal | None:
    return session.scalar(
        select(CompanySignal).where(
            CompanySignal.company_id == company_id,
            CompanySignal.canonical_url == canonical_url,
        )
    )


def existing_canonical_urls(session: Session, company_id: str) -> set[str]:
    rows = session.scalars(
        select(CompanySignal.canonical_url).where(
            CompanySignal.company_id == company_id
        )
    )
    return {url for url in rows if url}


def upsert_signal(
    session: Session,
    *,
    company_id: str,
    url: str,
    canonical_url: str,
    domain: str = "",
    source_type: str = "other",
    ownership: str = "unknown",
    confidence: float = 0.0,
    title: str = "",
    snippet: str = "",
    discovery_path: str = "",
    collector: str = "",
    detail: dict[str, Any] | None = None,
    seen_at: datetime | None = None,
    run_id: str | None = None,
) -> tuple[CompanySignal, bool]:
    """Insert or update a company signal. Returns (row, created)."""
    now = _as_utc(seen_at) or utc_now()
    row = get_by_canonical_url(session, company_id, canonical_url)
    if row is None:
        row = CompanySignal(
            company_id=company_id,
            url=url,
            canonical_url=canonical_url,
            domain=domain,
            source_type=source_type,
            ownership=ownership,
            confidence=confidence,
            title=title,
            snippet=snippet,
            discovery_path=discovery_path,
            collector=collector,
            detail=detail,
            first_seen_at=now,
            last_seen_at=now,
            last_run_id=run_id,
        )
        session.add(row)
        return row, True

    row.url = url or row.url
    row.domain = domain or row.domain
    row.source_type = source_type or row.source_type
    row.ownership = ownership or row.ownership
    if confidence:
        row.confidence = max(float(row.confidence or 0), float(confidence))
    if title:
        row.title = title
    if snippet:
        row.snippet = snippet
    if discovery_path:
        row.discovery_path = discovery_path
    if collector:
        row.collector = collector
    if detail:
        merged = dict(row.detail or {})
        merged.update(detail)
        row.detail = merged
    first_seen = _as_utc(row.first_seen_at)
    last_seen = _as_utc(row.last_seen_at)
    if first_seen is None or now < first_seen:
        row.first_seen_at = now
    if last_seen is None or now >= last_seen:
        row.last_seen_at = now
        if run_id:
            row.last_run_id = run_id
    elif run_id and not row.last_run_id:
        row.last_run_id = run_id
    row.updated_at = utc_now()
    return row, False
