"""Ingest OpenClaw / external collector signals into Vestige SQLite."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Run, RunSource, RunStatus, utc_now
from repositories import runs as runs_repo
from repositories import signals as signals_repo


def _host_of(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def run_kind(run: Run) -> str:
    snap = run.settings_snapshot or {}
    if snap.get("kind"):
        return str(snap["kind"])
    if snap.get("source") == "competitive-intel":
        return "signals"
    if snap.get("imported"):
        return "imported"
    return "footprint"


def existing_signal_urls(session: Session, company_id: str) -> set[str]:
    """URLs already in the company signal ledger (preferred) or historic runs."""
    known = signals_repo.existing_canonical_urls(session, company_id)
    if known:
        return known
    runs = runs_repo.list_runs(session, company_id=company_id, status=RunStatus.SUCCEEDED)
    urls: set[str] = set()
    for run in runs:
        if run_kind(run) != "signals":
            continue
        for source in runs_repo.list_run_sources(session, run.id):
            urls.add(source.canonical_url or source.url)
    return urls


def get_or_create_daily_signal_run(
    session: Session,
    *,
    company_id: str,
    day: str | None = None,
    collector: str = "openclaw",
) -> Run:
    day = day or date.today().isoformat()
    export_path = f"signals/daily/{day}"
    existing = session.scalar(
        select(Run).where(
            Run.company_id == company_id,
            Run.export_path == export_path,
        )
    )
    if existing is not None:
        return existing

    run = Run(
        company_id=company_id,
        status=RunStatus.SUCCEEDED,
        stage="succeeded",
        progress=100,
        settings_snapshot={
            "kind": "signals",
            "collector": collector,
            "day": day,
        },
        export_path=export_path,
        started_at=utc_now(),
        finished_at=utc_now(),
    )
    session.add(run)
    session.commit()
    return runs_repo.get_run(session, run.id)


def normalize_ingest_item(item: dict[str, Any]) -> dict[str, Any] | None:
    url = str(item.get("url") or "").strip()
    if not url.startswith("http"):
        return None
    return {
        "url": url,
        "canonical_url": str(item.get("canonical_url") or url).strip() or url,
        "domain": str(item.get("domain") or _host_of(url)),
        "source_type": str(item.get("source_type") or "other"),
        "ownership": str(item.get("ownership") or "unknown"),
        "confidence": float(item.get("confidence") or 0.5),
        "title": str(item.get("title") or ""),
        "snippet": str(item.get("snippet") or ""),
        "discovery_path": str(item.get("discovery_path") or item.get("source") or "ingest"),
        "bfs_round": int(item.get("bfs_round") or 0),
        "detail": item.get("detail")
        if isinstance(item.get("detail"), dict)
        else {
            k: item.get(k)
            for k in ("source", "category", "sentiment", "themes", "published")
            if item.get(k) is not None
        }
        or None,
    }


def ingest_signals(
    session: Session,
    *,
    company_id: str,
    items: list[dict[str, Any]],
    collector: str = "openclaw",
    day: str | None = None,
) -> dict[str, Any]:
    """Upsert company_signals (entity) and append first-seen rows to daily run (audit)."""
    day = day or date.today().isoformat()
    seen_batch: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    for raw in items:
        item = normalize_ingest_item(raw)
        if item is None:
            continue
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
            "run_id": None,
            "day": day,
        }

    # Ensure daily audit run exists when we have anything to process
    run = get_or_create_daily_signal_run(
        session, company_id=company_id, day=day, collector=collector
    )
    assert run is not None

    inserted = 0
    updated = 0
    audit_rows: list[RunSource] = []
    now = utc_now()

    for item in normalized_items:
        _row, created = signals_repo.upsert_signal(
            session,
            company_id=company_id,
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
            run_id=run.id,
        )
        if created:
            inserted += 1
            audit_rows.append(
                RunSource(
                    run_id=run.id,
                    url=item["url"],
                    canonical_url=item["canonical_url"],
                    domain=item["domain"],
                    source_type=item["source_type"],
                    ownership=item["ownership"],
                    confidence=item["confidence"],
                    title=item["title"],
                    snippet=item["snippet"],
                    discovery_path=item["discovery_path"],
                    bfs_round=item["bfs_round"],
                    detail=item["detail"],
                )
            )
        else:
            updated += 1

    for row in audit_rows:
        session.add(row)
    session.commit()

    runs_repo.append_run_event(
        session,
        run_id=run.id,
        stage="ingest",
        message=(
            f"Ingested via {collector}: {inserted} new, {updated} updated "
            f"({len(normalized_items)} in batch)"
        ),
        payload={
            "inserted": inserted,
            "updated": updated,
            "skipped": len(items) - len(normalized_items),
        },
    )
    run.finished_at = utc_now()
    run.status = RunStatus.SUCCEEDED
    run.stage = "succeeded"
    run.progress = 100
    session.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": len(items) - len(normalized_items),
        "run_id": run.id,
        "day": (run.settings_snapshot or {}).get("day") or day,
    }
