from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_KAGI_URL = "https://kagi.com/api/v1/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """Kagi Search API。"""
    import os

    api_key = os.getenv("KAGI_SEARCH_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 KAGI_SEARCH_API_KEY，请在 .env 配置后再使用 kagi 后端")

    headers = {"Authorization": f"Bearer {api_key}"}
    body = {"query": query, "limit": count}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_KAGI_URL, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    raw = payload.get("data", {}).get("search", [])
    results = normalize(raw[:count], engine="kagi")
    return filter_by_domains(results, filter_list)
