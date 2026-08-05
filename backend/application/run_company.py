from __future__ import annotations

from typing import Any

from pipeline import run_company_discovery


async def run_company(
    *,
    name: str,
    official_domain: str = "",
    industry: str = "",
    location: str = "",
    aliases: list[str] | None = None,
    settings: dict[str, Any] | None = None,
    output_dir: str | None = None,
    write_excel: bool = True,
) -> dict[str, Any]:
    """Run discovery for a request-scoped company identity."""
    anchor = {
        "name": name,
        "official_domain": official_domain or "",
        "industry": industry or "",
        "location": location or "",
        "aliases": list(aliases or []),
    }
    return await run_company_discovery(
        anchor=anchor,
        settings=settings,
        output_dir=output_dir,
        write_excel=write_excel,
    )
