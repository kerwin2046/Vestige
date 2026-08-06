from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import Company, utc_now
from schemas import CompanyCreate, CompanyUpdate


def list_companies(
    session: Session,
    *,
    tier: str | None = None,
    role: str | None = None,
    q: str | None = None,
    source: str | None = None,
    include_hidden: bool = False,
) -> list[Company]:
    stmt = select(Company)
    if not include_hidden:
        stmt = stmt.where(Company.directory_hidden == 0)
        stmt = stmt.where(Company.name != "通用")
    if tier:
        stmt = stmt.where(Company.tier == tier)
    if source:
        stmt = stmt.where(Company.source == source)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Company.name.ilike(like),
                Company.official_domain.ilike(like),
                Company.industry.ilike(like),
            )
        )
    items = list(session.scalars(stmt.order_by(Company.updated_at.desc())))
    if role:
        role_key = role.strip().lower()
        items = [
            company
            for company in items
            if role_key in [r.lower() for r in (company.roles or [])]
        ]
    return items


def get_company(session: Session, company_id: str) -> Company | None:
    return session.get(Company, company_id)


def create_company(session: Session, data: CompanyCreate) -> Company:
    company = Company(**data.model_dump())
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def update_company(
    session: Session, company: Company, data: CompanyUpdate
) -> Company:
    for key, value in data.model_dump().items():
        setattr(company, key, value)
    session.commit()
    session.refresh(company)
    return company


def promote_company(session: Session, company: Company, tier: str = "target") -> Company:
    company.tier = tier
    company.updated_at = utc_now()
    session.commit()
    session.refresh(company)
    return company


def delete_company(session: Session, company: Company) -> None:
    session.delete(company)
    session.commit()
