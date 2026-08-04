from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_MOJEEK_URL = "https://api.mojeek.com/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """Mojeek Search API。"""
    import os

    api_key = os.getenv("MOJEEK_SEARCH_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 MOJEEK_SEARCH_API_KEY，请在 .env 配置后再使用 mojeek 后端")

    headers = {"Accept": "application/json"}
    params = {"q": query, "api_key": api_key, "fmt": "json", "t": count}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(_MOJEEK_URL, headers=headers, params=params)
        resp.raise_for_status()
        payload = resp.json()

    raw = payload.get("response", {}).get("results", [])
    results = normalize(
        raw[:count],
        engine="mojeek",
        url_keys=("url", "link"),
    )
    # Mojeek 用 desc 作摘要
    for item, src in zip(results, raw[:count]):
        if not item.get("snippet") and isinstance(src, dict):
            item["snippet"] = src.get("desc") or ""
    return filter_by_domains(results, filter_list)
