"""Company-level signal ledger: backfill from historic signal runs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from application.ingest import run_kind
from models import RunStatus
from repositories import runs as runs_repo
from repositories import signals as signals_repo


def backfill_company_from_runs(
    session: Session, company_id: str
) -> dict[str, int]:
    """Materialize company_signals from all succeeded signal-kind runs."""
    runs = runs_repo.list_runs(
        session, company_id=company_id, status=RunStatus.SUCCEEDED
    )
    # Oldest first so first_seen sticks to earliest observation
    signal_runs = [r for r in runs if run_kind(r) == "signals"]
    signal_runs.sort(key=lambda r: r.created_at or r.started_at or r.finished_at)

    inserted = updated = skipped = 0
    for run in signal_runs:
        snap = run.settings_snapshot or {}
        collector = str(snap.get("collector") or snap.get("source") or "import")
        seen_at = run.finished_at or run.created_at
        for source in runs_repo.list_run_sources(session, run.id):
            url = (source.url or "").strip()
            if not url.startswith("http"):
                skipped += 1
                continue
            canonical = (source.canonical_url or url).strip() or url
            _row, created = signals_repo.upsert_signal(
                session,
                company_id=company_id,
                url=url,
                canonical_url=canonical,
                domain=source.domain or "",
                source_type=source.source_type or "other",
                ownership=source.ownership or "unknown",
                confidence=float(source.confidence or 0),
                title=source.title or "",
                snippet=source.snippet or "",
                discovery_path=source.discovery_path or "",
                collector=collector,
                detail=source.detail,
                seen_at=seen_at,
                run_id=run.id,
            )
            if created:
                inserted += 1
            else:
                updated += 1
    session.commit()
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def backfill_all_companies(session: Session) -> dict[str, int]:
    from repositories import companies as companies_repo

    totals = {"companies": 0, "inserted": 0, "updated": 0, "skipped": 0}
    for company in companies_repo.list_companies(session):
        stats = backfill_company_from_runs(session, company.id)
        if stats["inserted"] or stats["updated"]:
            totals["companies"] += 1
        totals["inserted"] += stats["inserted"]
        totals["updated"] += stats["updated"]
        totals["skipped"] += stats["skipped"]
    return totals
