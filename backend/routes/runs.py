from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_session
from models import Run, RunStatus
from repositories import companies, runs
from responses import success
from schemas import CompanyRead, RunCreate, RunSourceRead

router = APIRouter(tags=["runs"])


def _serialize(run: Run, *, include_company: bool = False) -> dict:
    data = {
        "id": run.id,
        "company_id": run.company_id,
        "previous_run_id": run.previous_run_id,
        "status": run.status.value,
        "stage": run.stage,
        "progress": run.progress,
        "settings_snapshot": run.settings_snapshot,
        "error": run.error,
        "export_path": run.export_path,
        "created_at": run.created_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
    if include_company:
        data["company"] = CompanyRead.model_validate(run.company).model_dump(
            mode="json"
        )
    return data


@router.post(
    "/api/companies/{company_id}/runs",
    status_code=status.HTTP_201_CREATED,
)
def create(
    company_id: str,
    data: RunCreate,
    session: Session = Depends(get_session),
):
    if companies.get_company(session, company_id) is None:
        raise HTTPException(status_code=404, detail="company not found")
    previous = runs.latest_successful_run(session, company_id)
    run = runs.create_run(
        session,
        company_id=company_id,
        settings_snapshot=data.snapshot(),
        previous_run_id=previous.id if previous else None,
    )
    return success(_serialize(run, include_company=True))


@router.get("/api/runs")
def list_all(
    company_id: str | None = Query(default=None),
    run_status: RunStatus | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
):
    items = runs.list_runs(session, company_id=company_id, status=run_status)
    return success([_serialize(run, include_company=True) for run in items])


@router.get("/api/runs/{run_id}")
def get(run_id: str, session: Session = Depends(get_session)):
    run = runs.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return success(_serialize(run, include_company=True))


@router.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str, session: Session = Depends(get_session)):
    run = runs.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
        raise HTTPException(status_code=409, detail="run cannot be cancelled")
    return success(_serialize(runs.request_cancel(session, run), include_company=True))


@router.get("/api/runs/{run_id}/sources")
def list_sources(run_id: str, session: Session = Depends(get_session)):
    run = runs.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    items = runs.list_run_sources(session, run_id)
    return success(
        [RunSourceRead.model_validate(item).model_dump(mode="json") for item in items]
    )


@router.post(
    "/api/runs/{run_id}/retry",
    status_code=status.HTTP_201_CREATED,
)
def retry(run_id: str, session: Session = Depends(get_session)):
    original = runs.get_run(session, run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="run not found")
    if original.status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="only terminal runs can be retried")
    run = runs.create_run(
        session,
        company_id=original.company_id,
        settings_snapshot=dict(original.settings_snapshot),
        previous_run_id=original.id,
    )
    return success(_serialize(run, include_company=True))

