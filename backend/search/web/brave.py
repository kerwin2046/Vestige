from __future__ import annotations

import asyncio

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_RATE_LIMIT_RETRY_DELAY = 1.0


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    import os

    api_key = os.getenv("BRAVE_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 BRAVE_API_KEY，请在 .env 配置后再使用 brave 后端")

    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": query, "count": count}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_BRAVE_ENDPOINT, params=params, headers=headers)
        if resp.status_code == 429:
            await asyncio.sleep(_RATE_LIMIT_RETRY_DELAY)
            resp = await client.get(_BRAVE_ENDPOINT, params=params, headers=headers)
        if resp.status_code != 200:
            print(f"⚠️ [brave] 状态码 {resp.status_code} query={query!r}: {resp.text[:200]}")
            return []
        payload = resp.json()

    raw = (payload.get("web", {}) or {}).get("results", [])
    results = normalize(raw[:count], engine="brave")
    return filter_by_domains(results, filter_list)
