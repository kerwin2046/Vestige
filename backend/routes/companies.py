from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from application.company_activity import activity_dict, activity_revision
from application.ingest import ingest_signals
from application.openclaw_agent import run_company_openclaw_agent
from application.scaffold_agent import agents_root, company_slug, scaffold_company_agent
from database import get_session
from repositories import companies
from repositories import signals as signals_repo
from responses import success
from schemas import (
    CompanyCreate,
    CompanyPromote,
    CompanyRead,
    CompanySignalRead,
    CompanyUpdate,
    IngestRequest,
)

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _read(company, *, include_activity: bool = False) -> dict:
    data = CompanyRead.model_validate(company).model_dump(mode="json")
    agent_dir = agents_root() / company_slug(company)
    data["agent_path"] = str(agent_dir) if agent_dir.exists() else None
    data["agent_slug"] = company_slug(company)
    if include_activity:
        data["activity"] = activity_dict(company)
    return data


@router.get("/activity-revision")
def get_activity_revision(session: Session = Depends(get_session)):
    """Cheap fingerprint — clients refetch directory only when this changes."""
    return success(activity_revision(session))


@router.get("")
def list_all(
    tier: str | None = Query(default=None),
    role: str | None = Query(default=None),
    q: str | None = Query(default=None),
    source: str | None = Query(default=None),
    include_activity: bool = Query(default=True),
    session: Session = Depends(get_session),
):
    items = companies.list_companies(
        session, tier=tier, role=role, q=q, source=source
    )
    return success(
        [_read(company, include_activity=include_activity) for company in items]
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create(data: CompanyCreate, session: Session = Depends(get_session)):
    company = companies.create_company(session, data)
    agent_path = None
    try:
        agent_path = str(scaffold_company_agent(company))
    except OSError:
        agent_path = None
    payload = _read(company)
    payload["agent_path"] = agent_path
    return success(payload)


@router.get("/{company_id}")
def get(company_id: str, session: Session = Depends(get_session)):
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    return success(_read(company, include_activity=True))


@router.put("/{company_id}")
def update(
    company_id: str,
    data: CompanyUpdate,
    session: Session = Depends(get_session),
):
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    return success(_read(companies.update_company(session, company, data)))


@router.post("/{company_id}/promote")
def promote(
    company_id: str,
    data: CompanyPromote | None = None,
    session: Session = Depends(get_session),
):
    """Promote a candidate into target/monitoring (Save as Target)."""
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    tier = (data.tier if data else "target") or "target"
    return success(_read(companies.promote_company(session, company, tier=tier)))


@router.delete("/{company_id}")
def delete(company_id: str, session: Session = Depends(get_session)):
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    companies.delete_company(session, company)
    return success({"deleted": True})


@router.post("/{company_id}/ingest")
def ingest(
    company_id: str,
    data: IngestRequest,
    session: Session = Depends(get_session),
):
    """OpenClaw / collectors push daily signals into Vestige SQLite (path A)."""
    if companies.get_company(session, company_id) is None:
        raise HTTPException(status_code=404, detail="company not found")
    result = ingest_signals(
        session,
        company_id=company_id,
        items=[item.model_dump() for item in data.items],
        collector=data.collector,
        day=data.day,
    )
    return success(result)


@router.get("/{company_id}/signals")
def list_signals(
    company_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """Company-level signal ledger (upserted; not tied to latest run)."""
    if companies.get_company(session, company_id) is None:
        raise HTTPException(status_code=404, detail="company not found")
    rows = signals_repo.list_company_signals(
        session, company_id, limit=limit, offset=offset
    )
    total = signals_repo.count_company_signals(session, company_id)
    return success(
        {
            "items": [
                CompanySignalRead.model_validate(row).model_dump(mode="json")
                for row in rows
            ],
            "total": total,
        }
    )


@router.post("/{company_id}/scaffold-agent")
def scaffold_agent(company_id: str, session: Session = Depends(get_session)):
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    path = scaffold_company_agent(company)
    return success({"agent_path": str(path), "slug": path.name})


@router.post("/{company_id}/run-agent")
def run_agent(
    company_id: str,
    wait: bool = Query(default=False),
    local: bool = Query(default=False),
    timeout: int = Query(default=600, ge=30, le=3600),
    shared: bool | None = Query(
        default=None,
        description="Use shared signals-collector (default from VESTIGE_SHARED_COLLECTOR).",
    ),
    session: Session = Depends(get_session),
):
    """Trigger OpenClaw to execute this company's agent workspace.

    Default uses the shared signals-collector (one agent, many companies).
    Pass shared=false to use the legacy per-company agent directory.
    Default is detached (returns immediately with pid + log_path).
    Pass wait=true to block until the OpenClaw turn finishes.
    """
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    try:
        from application.signals_collector import (
            run_shared_collector_for_company,
            use_shared_collector_by_default,
        )

        use_shared = shared if shared is not None else use_shared_collector_by_default()
        if use_shared:
            result = run_shared_collector_for_company(
                company,
                wait=wait,
                local=local,
                timeout_seconds=timeout,
            )
        else:
            result = run_company_openclaw_agent(
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
