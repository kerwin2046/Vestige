from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

TAVILY_ENDPOINT = "https://api.tavily.com/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    import os

    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 TAVILY_API_KEY，请在 .env 配置后再使用 tavily 后端")

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
