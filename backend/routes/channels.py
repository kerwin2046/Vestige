from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_session
from models import Channel
from responses import success
from schemas import ChannelRead

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _serialize(channel: Channel) -> dict:
    return ChannelRead.model_validate(channel).model_dump(mode="json")


@router.get("")
def list_channels(
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    country: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    stmt = select(Channel)
    if kind:
        stmt = stmt.where(Channel.kind == kind)
    if industry:
        stmt = stmt.where(Channel.industry == industry)
    if country:
        stmt = stmt.where(Channel.country == country)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Channel.name.ilike(like),
                Channel.domain.ilike(like),
                Channel.url.ilike(like),
                Channel.channel_type.ilike(like),
            )
        )
    stmt = stmt.order_by(Channel.score.desc(), Channel.name.asc()).offset(offset).limit(limit)
    items = list(session.scalars(stmt))
    return success([_serialize(item) for item in items])


@router.get("/stats")
def channel_stats(session: Session = Depends(get_session)):
    total = session.scalar(select(func.count()).select_from(Channel)) or 0
    platform_count = (
        session.scalar(
            select(func.count()).select_from(Channel).where(Channel.kind == "platform")
        )
        or 0
    )
    association_count = (
        session.scalar(
            select(func.count())
            .select_from(Channel)
            .where(Channel.kind == "association")
        )
        or 0
    )
    with_directory = (
        session.scalar(
            select(func.count())
            .select_from(Channel)
            .where(Channel.has_member_directory == 1)
        )
        or 0
    )
    return success(
        {
            "total": total,
            "platform_count": platform_count,
            "association_count": association_count,
            "with_member_directory": with_directory,
        }
    )
