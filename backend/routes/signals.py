"""API for shared signals collector dispatch."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from application.signals_collector import (
    COLLECTOR_SLUG,
    dispatch_signals,
    run_shared_collector_for_company,
    scaffold_signals_collector,
    select_dispatch_queue,
)
from database import get_session
from repositories import companies
from responses import success

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.post("/scaffold-collector")
def scaffold_collector():
    path = scaffold_signals_collector()
    return success({"agent_path": str(path), "slug": COLLECTOR_SLUG})


@router.get("/queue")
def preview_queue(
    limit: int = Query(default=10, ge=1, le=100),
    tier: str | None = Query(default="monitoring"),
    role: str | None = Query(default=None),
    stale_only: bool = Query(default=True),
    session: Session = Depends(get_session),
):
    items = select_dispatch_queue(
        session, limit=limit, tier=tier, role=role, stale_only=stale_only
    )
    return success(
        {
            "count": len(items),
            "items": [
                {
                    "id": c.id,
                    "name": c.name,
                    "tier": c.tier,
                    "priority": c.priority,
                    "last_signal_at": c.last_signal_at.isoformat()
                    if c.last_signal_at
                    else None,
                    "signal_count": c.signal_count or 0,
                }
                for c in items
            ],
        }
    )


@router.post("/dispatch")
def dispatch(
    limit: int = Query(default=5, ge=1, le=50),
    tier: str | None = Query(default="monitoring"),
    role: str | None = Query(default=None),
    stale_only: bool = Query(default=True),
    wait: bool = Query(default=False),
    local: bool = Query(default=False),
    timeout: int = Query(default=600, ge=30, le=3600),
    session: Session = Depends(get_session),
):
    """Dispatch up to `limit` companies through the shared OpenClaw collector."""
    try:
        result = dispatch_signals(
            session,
            limit=limit,
            tier=tier,
            role=role,
            stale_only=stale_only,
            wait=wait,
            local=local,
            timeout_seconds=timeout,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success(result)


@router.post("/dispatch/{company_id}")
def dispatch_one(
    company_id: str,
    wait: bool = Query(default=False),
    local: bool = Query(default=False),
    timeout: int = Query(default=600, ge=30, le=3600),
    session: Session = Depends(get_session),
):
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    try:
        result = run_shared_collector_for_company(
            company,
            wait=wait,
            local=local,
            timeout_seconds=timeout,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return success(result)
