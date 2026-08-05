from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_session
from models import Company, Run, RunSource, RunStatus
from repositories import runs
from responses import success
from routes.runs import _serialize

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(session: Session = Depends(get_session)):
    company_count = session.scalar(select(func.count()).select_from(Company)) or 0
    run_count = session.scalar(select(func.count()).select_from(Run)) or 0
    queued_count = (
        session.scalar(
            select(func.count())
            .select_from(Run)
            .where(Run.status == RunStatus.QUEUED)
        )
        or 0
    )
    source_count = session.scalar(select(func.count()).select_from(RunSource)) or 0
    recent_runs = runs.list_runs(session)[:10]
    return success(
        {
            "company_count": company_count,
            "run_count": run_count,
            "queued_count": queued_count,
            "source_count": source_count,
            "recent_runs": [
                _serialize(run, include_company=True) for run in recent_runs
            ],
        }
    )

