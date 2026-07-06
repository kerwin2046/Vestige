from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_GOOGLE_PSE_URL = "https://www.googleapis.com/customsearch/v1"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """Google Programmable Search Engine（Custom Search JSON API）。"""
    import os

    api_key = os.getenv("GOOGLE_PSE_API_KEY", "")
    engine_id = os.getenv("GOOGLE_PSE_ENGINE_ID", "")
    if not api_key or not engine_id:
        raise RuntimeError(
            "缺少 GOOGLE_PSE_API_KEY 或 GOOGLE_PSE_ENGINE_ID，请在 .env 配置后再使用 google_pse 后端"
        )

    referer = os.getenv("GOOGLE_PSE_REFERER", "").strip()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if referer:
        headers["Referer"] = referer

    all_items: list[dict] = []
    start_index = 1
    remaining = count

    async with httpx.AsyncClient(timeout=30.0) as client:
        while remaining > 0:
            page_size = min(remaining, 10)
            params = {
                "cx": engine_id,
                "q": query,
                "key": api_key,
                "num": str(page_size),
                "start": str(start_index),
            }
            resp = await client.get(_GOOGLE_PSE_URL, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()

            items = payload.get("items", [])
            if not items:
                break

            all_items.extend(items)
            remaining -= len(items)
            start_index += 10

    results = normalize(all_items[:count], engine="google_pse", url_keys=("link", "url"))
    return filter_by_domains(results, filter_list)
