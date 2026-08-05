from __future__ import annotations

import asyncio

from search.web._filter import filter_by_domains
from search.web.main import normalize


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    def _sync() -> list[dict]:
        from ddgs import DDGS

        with DDGS() as d:
            try:
                return d.text(query, max_results=count, safesearch="off")
            except Exception as e:
                if "no results" in str(e).lower():
                    return []
                raise

    raw = await asyncio.to_thread(_sync)
    results = normalize(raw or [], engine="duckduckgo")
    return filter_by_domains(results, filter_list)
