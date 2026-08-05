from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Company
from schemas import CompanyCreate, CompanyUpdate


def list_companies(session: Session) -> list[Company]:
    return list(session.scalars(select(Company).order_by(Company.created_at.desc())))


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


def delete_company(session: Session, company: Company) -> None:
    session.delete(company)
    session.commit()

