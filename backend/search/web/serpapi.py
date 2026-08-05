from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_SERPAPI_URL = "https://serpapi.com/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """SerpApi.com — 多引擎 SERP（默认 Google）。"""
    import os

    from config import SERPAPI_ENGINE

    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 SERPAPI_API_KEY，请在 .env 配置后再使用 serpapi 后端")

    engine = (os.getenv("SERPAPI_ENGINE") or SERPAPI_ENGINE or "google").strip()
    params = {"engine": engine, "q": query, "api_key": api_key}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(_SERPAPI_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    if payload.get("error"):
        raise RuntimeError(payload.get("error"))

    organic = sorted(
        payload.get("organic_results", []),
        key=lambda item: item.get("position", 0),
    )
    results = normalize(organic[:count], engine="serpapi", url_keys=("link", "url"))
    return filter_by_domains(results, filter_list)
