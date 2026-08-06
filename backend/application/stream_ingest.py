"""Ingest collector payloads into Intel Streams (no fake company)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from application.ingest import normalize_ingest_item
from models import utc_now
from repositories import stream_signals as streams_repo


def ingest_stream_signals(
    session: Session,
    *,
    stream_id: str,
    items: list[dict[str, Any]],
    collector: str = "openclaw:mfg-social-pulse",
    day: str | None = None,
) -> dict[str, Any]:
    """Upsert stream_signals ledger. No Run row (streams are not companies)."""
    day = day or date.today().isoformat()
    seen_batch: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    for raw in items:
        item = normalize_ingest_item(raw)
        if item is None:
            continue
        # Prefer community/social defaults for market streams when unspecified
        if item["source_type"] == "other" and not raw.get("source_type"):
            source_hint = str(raw.get("source") or item.get("discovery_path") or "").lower()
            if any(k in source_hint for k in ("reddit", "forum", "linkedin", "machinist")):
                item["source_type"] = "community_ugc"
            elif "social" in source_hint:
                item["source_type"] = "social"
        key = item["canonical_url"]
        if key in seen_batch:
            continue
        seen_batch.add(key)
        normalized_items.append(item)

    if not normalized_items:
        return {
            "inserted": 0,
            "updated": 0,
            "skipped": len(items),
            "stream_id": stream_id,
            "day": day,
        }

    inserted = 0
    updated = 0
    now = utc_now()
    for item in normalized_items:
        _row, created = streams_repo.upsert_stream_signal(
            session,
            stream_id=stream_id,
            url=item["url"],
            canonical_url=item["canonical_url"],
            domain=item["domain"],
            source_type=item["source_type"],
            ownership=item["ownership"],
            confidence=item["confidence"],
            title=item["title"],
            snippet=item["snippet"],
            discovery_path=item["discovery_path"],
            collector=collector,
            detail=item["detail"],
            seen_at=now,
        )
        if created:
            inserted += 1
        else:
            updated += 1

    session.commit()
    streams_repo.refresh_stream_activity(session, stream_id)

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": len(items) - len(normalized_items),
        "stream_id": stream_id,
        "day": day,
    }
