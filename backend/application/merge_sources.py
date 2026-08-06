"""Incremental footprint inventory merge (by canonical URL)."""

from __future__ import annotations

from typing import Any

from models import Run, RunSource, RunStatus
from sqlalchemy import select
from sqlalchemy.orm import Session


def run_kind(run: Run) -> str:
    snap = run.settings_snapshot or {}
    if snap.get("kind"):
        return str(snap["kind"])
    if snap.get("source") == "competitive-intel":
        return "signals"
    if snap.get("imported"):
        return "imported"
    return "footprint"


def is_footprint_run(run: Run) -> bool:
    return run_kind(run) not in {"signals"}


def source_key(item: dict[str, Any] | RunSource) -> str:
    if isinstance(item, RunSource):
        return (item.canonical_url or item.url or "").strip().lower()
    return (item.get("canonical_url") or item.get("url") or "").strip().lower()


def source_to_dict(row: RunSource) -> dict[str, Any]:
    return {
        "url": row.url,
        "canonical_url": row.canonical_url or row.url,
        "domain": row.domain or "",
        "source_type": row.source_type or "other",
        "ownership": row.ownership or "unknown",
        "confidence": float(row.confidence or 0.0),
        "title": row.title or "",
        "snippet": row.snippet or "",
        "discovery_path": row.discovery_path or "",
        "bfs_round": int(row.bfs_round or 0),
        "detail": dict(row.detail) if isinstance(row.detail, dict) else row.detail,
    }


def _prefer_text(old: str, new: str) -> str:
    old = (old or "").strip()
    new = (new or "").strip()
    if not old:
        return new
    if not new:
        return old
    return new if len(new) >= len(old) else old


def merge_footprint_sources(
    base: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge inventories by canonical_url.

    - New URLs are appended.
    - Existing URLs keep the higher confidence; fill empty fields; refresh title/snippet
      when confidence is not lower.
    """
    by_key: dict[str, dict[str, Any]] = {}
    base_keys: set[str] = set()
    for item in base:
        key = source_key(item)
        if not key:
            continue
        by_key[key] = dict(item)
        by_key[key]["canonical_url"] = item.get("canonical_url") or item.get("url") or ""
        base_keys.add(key)

    added = 0
    updated = 0
    incoming_keys: set[str] = set()
    for item in incoming:
        key = source_key(item)
        if not key:
            continue
        incoming_keys.add(key)
        payload = dict(item)
        payload["canonical_url"] = item.get("canonical_url") or item.get("url") or ""
        if key not in by_key:
            detail = dict(payload.get("detail") or {}) if isinstance(payload.get("detail"), dict) else {}
            detail["merge"] = "added"
            payload["detail"] = detail
            by_key[key] = payload
            added += 1
            continue

        prev = by_key[key]
        new_conf = float(payload.get("confidence") or 0.0)
        old_conf = float(prev.get("confidence") or 0.0)
        changed = False
        if new_conf >= old_conf:
            for field in (
                "url",
                "canonical_url",
                "domain",
                "source_type",
                "ownership",
                "confidence",
                "discovery_path",
                "bfs_round",
            ):
                if payload.get(field) is not None and payload.get(field) != "":
                    if prev.get(field) != payload.get(field):
                        prev[field] = payload[field]
                        changed = True
            title = _prefer_text(prev.get("title") or "", payload.get("title") or "")
            snippet = _prefer_text(prev.get("snippet") or "", payload.get("snippet") or "")
            if title != (prev.get("title") or ""):
                prev["title"] = title
                changed = True
            if snippet != (prev.get("snippet") or ""):
                prev["snippet"] = snippet
                changed = True
            if isinstance(payload.get("detail"), dict):
                detail = dict(prev.get("detail") or {}) if isinstance(prev.get("detail"), dict) else {}
                detail.update(payload["detail"])
                prev["detail"] = detail
                changed = True
        else:
            for field in ("title", "snippet", "domain", "source_type", "ownership"):
                if not (prev.get(field) or "") and (payload.get(field) or ""):
                    prev[field] = payload[field]
                    changed = True

        if changed:
            detail = dict(prev.get("detail") or {}) if isinstance(prev.get("detail"), dict) else {}
            detail["merge"] = "updated"
            prev["detail"] = detail
            updated += 1

    kept = len(base_keys - incoming_keys)
    merged = list(by_key.values())
    merged.sort(
        key=lambda s: (-float(s.get("confidence") or 0.0), (s.get("domain") or "").lower())
    )
    return merged, {
        "added": added,
        "updated": updated,
        "kept": kept,
        "total": len(merged),
        "base": len(base_keys),
        "incoming": len(incoming_keys),
    }


def latest_successful_footprint_run(
    session: Session,
    company_id: str,
    *,
    exclude_run_id: str | None = None,
) -> Run | None:
    statement = (
        select(Run)
        .where(
            Run.company_id == company_id,
            Run.status == RunStatus.SUCCEEDED,
        )
        .order_by(Run.finished_at.desc(), Run.created_at.desc())
    )
    for run in session.scalars(statement):
        if exclude_run_id and run.id == exclude_run_id:
            continue
        if is_footprint_run(run):
            return run
    return None
