from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from application.ingest import ingest_signals
from application.scaffold_agent import scaffold_company_agent
from database import get_session
from repositories import companies
from responses import success
from schemas import CompanyCreate, CompanyRead, CompanyUpdate, IngestRequest

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _read(company) -> dict:
    return CompanyRead.model_validate(company).model_dump(mode="json")


@router.get("")
def list_all(session: Session = Depends(get_session)):
    return success([_read(company) for company in companies.list_companies(session)])


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
    return success(_read(company))


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


@router.post("/{company_id}/scaffold-agent")
def scaffold_agent(company_id: str, session: Session = Depends(get_session)):
    company = companies.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    path = scaffold_company_agent(company)
    return success({"agent_path": str(path), "slug": path.name})
