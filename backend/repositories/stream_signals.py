"""Intel stream + stream signal repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models import IntelStream, StreamSignal, utc_now

MFG_SOCIAL_DEFAULT_SOURCES: dict[str, Any] = {
    "platforms": [
        {
            "id": "practicalmachinist",
            "name": "Practical Machinist",
            "url": "https://www.practicalmachinist.com/",
            "kind": "forum",
        },
        {
            "id": "reddit",
            "name": "Reddit",
            "subs": ["Machinists", "CNC", "manufacturing", "AdditiveManufacturing"],
            "kind": "social",
        },
        {
            "id": "linkedin",
            "name": "LinkedIn",
            "queries": [
                "CNC machining",
                "contract manufacturing",
                "metal 3D printing",
                "job shop capacity",
            ],
            "kind": "social",
        },
    ],
    "topics": [
        "CNC / machining capacity",
        "additive / metal 3D printing",
        "lead times and quoting",
        "shop floor tooling",
        "manufacturing labor / hiring",
    ],
}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def list_streams(
    session: Session,
    *,
    status: str | None = "active",
    kind: str | None = None,
) -> list[IntelStream]:
    stmt = select(IntelStream)
    if status:
        stmt = stmt.where(IntelStream.status == status)
    if kind:
        stmt = stmt.where(IntelStream.kind == kind)
    return list(session.scalars(stmt.order_by(IntelStream.name.asc())))


def get_stream(session: Session, stream_id: str) -> IntelStream | None:
    return session.get(IntelStream, stream_id)


def get_stream_by_slug(session: Session, slug: str) -> IntelStream | None:
    return session.scalar(select(IntelStream).where(IntelStream.slug == slug))


def resolve_stream(session: Session, id_or_slug: str) -> IntelStream | None:
    row = get_stream(session, id_or_slug)
    if row is not None:
        return row
    return get_stream_by_slug(session, id_or_slug)


def ensure_mfg_social_stream(session: Session) -> IntelStream:
    existing = get_stream_by_slug(session, "mfg-social")
    if existing is not None:
        if not existing.sources:
            existing.sources = MFG_SOCIAL_DEFAULT_SOURCES
            session.commit()
            session.refresh(existing)
        return existing
    stream = IntelStream(
        slug="mfg-social",
        name="Manufacturing Social Pulse",
        kind="market_social",
        status="active",
        description=(
            "Industry community heat: Reddit, LinkedIn, Practical Machinist, "
            "and related manufacturing forums — not tied to a single company."
        ),
        sources=MFG_SOCIAL_DEFAULT_SOURCES,
        collector="openclaw:mfg-social-pulse",
        agent_slug="mfg-social-pulse",
    )
    session.add(stream)
    session.commit()
    session.refresh(stream)
    return stream


def list_stream_signals(
    session: Session,
    stream_id: str,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[StreamSignal]:
    stmt = (
        select(StreamSignal)
        .where(StreamSignal.stream_id == stream_id)
        .order_by(StreamSignal.last_seen_at.desc(), StreamSignal.id.desc())
        .offset(max(0, offset))
    )
    if limit is not None:
        stmt = stmt.limit(max(1, limit))
    return list(session.scalars(stmt))


def count_stream_signals(session: Session, stream_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(StreamSignal)
            .where(StreamSignal.stream_id == stream_id)
        )
        or 0
    )


def list_recent_stream_signals(
    session: Session,
    *,
    limit: int = 200,
    since: datetime | None = None,
) -> list[StreamSignal]:
    stmt = select(StreamSignal).order_by(StreamSignal.last_seen_at.desc())
    if since is not None:
        since_utc = _as_utc(since) or since
        since_naive = since_utc.replace(tzinfo=None)
        stmt = stmt.where(StreamSignal.last_seen_at >= since_naive)
    return list(session.scalars(stmt.limit(max(1, limit))))


def get_by_canonical_url(
    session: Session, stream_id: str, canonical_url: str
) -> StreamSignal | None:
    return session.scalar(
        select(StreamSignal).where(
            StreamSignal.stream_id == stream_id,
            StreamSignal.canonical_url == canonical_url,
        )
    )


def upsert_stream_signal(
    session: Session,
    *,
    stream_id: str,
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
) -> tuple[StreamSignal, bool]:
    now = _as_utc(seen_at) or utc_now()
    row = get_by_canonical_url(session, stream_id, canonical_url)
    if row is None:
        row = StreamSignal(
            stream_id=stream_id,
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
    row.updated_at = utc_now()
    return row, False


def refresh_stream_activity(session: Session, stream_id: str) -> IntelStream | None:
    stream = get_stream(session, stream_id)
    if stream is None:
        return None
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_naive = today.replace(tzinfo=None)
    total = count_stream_signals(session, stream_id)
    today_count = int(
        session.scalar(
            select(func.count())
            .select_from(StreamSignal)
            .where(
                StreamSignal.stream_id == stream_id,
                StreamSignal.last_seen_at >= today_naive,
            )
        )
        or 0
    )
    last_seen = session.scalar(
        select(func.max(StreamSignal.last_seen_at)).where(
            StreamSignal.stream_id == stream_id
        )
    )
    stream.signal_count = total
    stream.signals_today = today_count
    stream.last_signal_at = last_seen
    stream.activity_updated_at = utc_now()
    session.commit()
    session.refresh(stream)
    return stream


def find_dump_companies(session: Session) -> list:
    """Companies that should leave the directory after stream migration."""
    from models import Company

    return list(
        session.scalars(
            select(Company).where(
                or_(
                    Company.name == "通用",
                    Company.directory_hidden == 1,
                )
            )
        )
    )
