from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_DEFAULT_API_URL = "https://api.perplexity.ai/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """Perplexity Search API（非 Chat Completions）。"""
    import os

    api_key = os.getenv("PERPLEXITY_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 PERPLEXITY_API_KEY，请在 .env 配置后再使用 perplexity 后端")

    api_url = os.getenv("PERPLEXITY_SEARCH_API_URL", _DEFAULT_API_URL)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"query": query, "max_results": count}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(api_url, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    results = normalize(payload.get("results", [])[:count], engine="perplexity")
    return filter_by_domains(results, filter_list)
