"""Ranked competitive pulse feed (recency × confidence × company weight)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models import Company, CompanySignal
from repositories.signals import _as_utc


TYPE_WEIGHTS: dict[str, float] = {
    "news_media": 1.25,
    "public_record": 1.3,
    "owned": 1.05,
    "social": 0.95,
    "community_ugc": 0.9,
    "recruitment": 0.85,
    "marketplace_directory": 0.8,
    "other": 0.75,
}

TIER_WEIGHTS: dict[str, float] = {
    "monitoring": 1.35,
    "target": 1.0,
    "candidate": 0.7,
}

PRIORITY_WEIGHTS: dict[str, float] = {
    "critical": 1.4,
    "high": 1.25,
    "p0": 1.4,
    "p1": 1.25,
    "medium": 1.05,
    "low": 0.85,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def company_weight(company: Company | None) -> float:
    if company is None:
        return 1.0
    tier = str(getattr(company, "tier", "") or "target").strip().lower()
    priority = str(getattr(company, "priority", "") or "").strip().lower()
    weight = TIER_WEIGHTS.get(tier, 1.0)
    if priority:
        weight *= PRIORITY_WEIGHTS.get(priority, 1.0)
    return weight


def type_weight(source_type: str | None) -> float:
    key = str(source_type or "other").strip().lower()
    return TYPE_WEIGHTS.get(key, 0.85)


def recency_weight(seen_at: datetime | None, *, now: datetime | None = None) -> float:
    """Half-life ~12h; clamps to a small floor so older items can still rank."""
    current = now or _now()
    seen = _as_utc(seen_at)
    if seen is None:
        return 0.05
    age_hours = max(0.0, (current - seen).total_seconds() / 3600.0)
    return max(0.05, math.exp(-math.log(2) * age_hours / 12.0))


def score_signal(
    row: CompanySignal,
    *,
    now: datetime | None = None,
) -> float:
    confidence = max(0.0, min(1.0, float(row.confidence or 0.0)))
    return (
        confidence
        * recency_weight(row.last_seen_at, now=now)
        * company_weight(getattr(row, "company", None))
        * type_weight(row.source_type)
    )


def priority_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"


@dataclass
class FeedWindow:
    key: str
    since: datetime
    label: str


def resolve_windows(now: datetime | None = None) -> list[FeedWindow]:
    current = now or _now()
    start_today = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        FeedWindow("today", start_today, "Today"),
        FeedWindow("24h", current - timedelta(hours=24), "Last 24 hours"),
        FeedWindow("7d", current - timedelta(days=7), "Last 7 days"),
    ]


def _load_candidates(
    session: Session, since: datetime, *, hard_limit: int = 800
) -> list[CompanySignal]:
    # SQLite often stores datetimes without tz; compare in naive UTC.
    since_utc = _as_utc(since) or since
    since_naive = since_utc.replace(tzinfo=None)
    return list(
        session.scalars(
            select(CompanySignal)
            .options(joinedload(CompanySignal.company))
            .where(CompanySignal.last_seen_at >= since_naive)
            .order_by(CompanySignal.last_seen_at.desc())
            .limit(hard_limit)
        ).unique()
    )


def _rank(
    rows: list[CompanySignal],
    *,
    now: datetime | None = None,
    min_confidence: float = 0.0,
) -> list[tuple[CompanySignal, float]]:
    current = now or _now()
    scored: list[tuple[CompanySignal, float]] = []
    for row in rows:
        conf = float(row.confidence or 0.0)
        if conf < min_confidence:
            continue
        scored.append((row, score_signal(row, now=current)))
    scored.sort(key=lambda item: (item[1], _as_utc(item[0].last_seen_at) or current), reverse=True)
    return scored


def build_pulse_feed(
    session: Session,
    *,
    limit: int = 25,
    offset: int = 0,
    pin_limit: int = 6,
    min_fill: int = 12,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Auto-expand window: today High/Medium → 24h → 7d; score-rank; pin must-see."""
    current = now or _now()
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    pin_limit = max(0, min(pin_limit, 12))

    windows = resolve_windows(current)
    chosen = windows[0]
    ranked: list[tuple[CompanySignal, float]] = []

    for window in windows:
        candidates = _load_candidates(session, window.since)
        preferred = _rank(candidates, now=current, min_confidence=0.5)
        chosen = window
        ranked = preferred
        if len(preferred) >= min_fill:
            break

    if len(ranked) < min_fill:
        ranked = _rank(
            _load_candidates(session, chosen.since),
            now=current,
            min_confidence=0.0,
        )

    must_see_pairs = [
        (row, score)
        for row, score in ranked
        if float(row.confidence or 0) >= 0.8
    ][:pin_limit]
    if len(must_see_pairs) < min(3, pin_limit) and ranked:
        must_see_pairs = ranked[:pin_limit]

    must_see_ids = {row.id for row, _ in must_see_pairs}
    remainder = [(row, score) for row, score in ranked if row.id not in must_see_ids]

    page = remainder[offset : offset + limit]
    total_remainder = len(remainder)
    has_more = offset + limit < total_remainder

    def pack(row: CompanySignal, score: float) -> dict[str, Any]:
        return {
            "row": row,
            "score": round(score, 4),
            "priority": priority_label(float(row.confidence or 0)),
        }

    return {
        "window": chosen.key,
        "window_label": chosen.label,
        "must_see": [pack(row, score) for row, score in must_see_pairs],
        "feed": [pack(row, score) for row, score in page],
        "feed_total": total_remainder,
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": offset + len(page) if has_more else offset,
        "candidate_count": len(ranked),
    }
