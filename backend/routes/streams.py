"""API for Intel Streams (market / topic lenses)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from application.stream_ingest import ingest_stream_signals
from database import get_session
from repositories import stream_signals as streams_repo
from responses import success
from schemas import IngestRequest, IntelStreamRead, StreamSignalRead

router = APIRouter(prefix="/api/streams", tags=["streams"])


def _read_stream(stream) -> dict:
    return IntelStreamRead.model_validate(stream).model_dump(mode="json")


@router.get("")
def list_streams(
    status: str | None = Query(default="active"),
    kind: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    items = streams_repo.list_streams(session, status=status, kind=kind)
    return success([_read_stream(s) for s in items])


@router.get("/{id_or_slug}")
def get_stream(id_or_slug: str, session: Session = Depends(get_session)):
    stream = streams_repo.resolve_stream(session, id_or_slug)
    if stream is None:
        raise HTTPException(status_code=404, detail="stream not found")
    return success(_read_stream(stream))


@router.get("/{id_or_slug}/signals")
def list_signals(
    id_or_slug: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    stream = streams_repo.resolve_stream(session, id_or_slug)
    if stream is None:
        raise HTTPException(status_code=404, detail="stream not found")
    items = streams_repo.list_stream_signals(
        session, stream.id, limit=limit, offset=offset
    )
    total = streams_repo.count_stream_signals(session, stream.id)
    return success(
        {
            "items": [
                StreamSignalRead.model_validate(row).model_dump(mode="json")
                for row in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/{id_or_slug}/ingest")
def ingest(
    id_or_slug: str,
    body: IngestRequest,
    session: Session = Depends(get_session),
):
    stream = streams_repo.resolve_stream(session, id_or_slug)
    if stream is None:
        raise HTTPException(status_code=404, detail="stream not found")
    result = ingest_stream_signals(
        session,
        stream_id=stream.id,
        items=[item.model_dump() for item in body.items],
        collector=body.collector or stream.collector or "openclaw:mfg-social-pulse",
        day=body.day,
    )
    return success(result)


@router.post("/{id_or_slug}/scaffold-agent")
def scaffold_agent(id_or_slug: str, session: Session = Depends(get_session)):
    stream = streams_repo.resolve_stream(session, id_or_slug)
    if stream is None:
        raise HTTPException(status_code=404, detail="stream not found")
    from application.stream_agent import AGENT_SLUG, scaffold_mfg_social_agent

    path = scaffold_mfg_social_agent()
    return success(
        {
            "agent_path": str(path),
            "slug": AGENT_SLUG,
            "stream_id": stream.id,
            "stream_slug": stream.slug,
        }
    )


@router.post("/{id_or_slug}/run-agent")
def run_agent(
    id_or_slug: str,
    wait: bool = Query(default=False),
    local: bool = Query(default=False),
    timeout: int = Query(default=600, ge=30, le=3600),
    session: Session = Depends(get_session),
):
    """Start OpenClaw stream collector (detached by default)."""
    stream = streams_repo.resolve_stream(session, id_or_slug)
    if stream is None:
        raise HTTPException(status_code=404, detail="stream not found")
    try:
        from application.stream_agent import run_mfg_social_pulse

        result = run_mfg_social_pulse(
            session,
            stream=stream,
            wait=wait,
            local=local,
            timeout_seconds=timeout,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return success(result)
