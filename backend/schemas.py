from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    official_domain: str = Field(default="", max_length=255)
    industry: str = Field(default="", max_length=255)
    location: str = Field(default="", max_length=255)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("company name is required")
        return value

    @field_validator("official_domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            return ""
        parsed = urlsplit(value if "://" in value else f"//{value}")
        domain = (parsed.hostname or "").lower()
        return domain.removeprefix("www.")

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            alias = value.strip()
            if alias and alias not in result:
                result.append(alias)
        return result


class CompanyUpdate(CompanyCreate):
    pass


class CompanyRead(CompanyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    search_backend: str | None = None
    max_urls_to_crawl: int | None = Field(default=None, ge=0, le=500)

    def snapshot(self) -> dict:
        data = {
            key: value
            for key, value in self.model_dump().items()
            if value is not None
        }
        data.setdefault("kind", "footprint")
        return data


class IngestItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str = Field(min_length=8)
    title: str = ""
    snippet: str = ""
    source: str | None = None
    source_type: str | None = None
    ownership: str | None = None
    category: str | None = None
    sentiment: str | None = None
    themes: str | None = None
    published: str | None = None
    confidence: float | None = None
    domain: str | None = None
    canonical_url: str | None = None
    discovery_path: str | None = None
    detail: dict[str, Any] | None = None


class IngestRequest(BaseModel):
    collector: str = "openclaw"
    day: str | None = None
    items: list[IngestItem] = Field(default_factory=list)


class RunSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    url: str
    canonical_url: str
    domain: str
    source_type: str
    ownership: str
    confidence: float
    title: str
    snippet: str
    discovery_path: str
    bfs_round: int
    detail: dict[str, Any] | None = None

