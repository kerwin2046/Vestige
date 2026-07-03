from __future__ import annotations

import httpx

from search.adapters._filter import filter_by_domains
from search.adapters._types import normalize

TAVILY_ENDPOINT = "https://api.tavily.com/search"


async def search(
    api_key: str,
    query: str,
    count: int,
    filter_list: list[str] | None = None,
) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            TAVILY_ENDPOINT,
            headers=headers,
            json={"query": query, "max_results": count},
        )
        resp.raise_for_status()
        payload = resp.json()

    results = normalize(payload.get("results", [])[:count], engine="tavily")
    return filter_by_domains(results, filter_list)
