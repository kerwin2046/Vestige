from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

DEFAULT_BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    import os

    from config import BING_LOCALE, BING_SEARCH_V7_ENDPOINT

    subscription_key = os.getenv("BING_SEARCH_V7_SUBSCRIPTION_KEY", "")
    if not subscription_key:
        raise RuntimeError(
            "缺少 BING_SEARCH_V7_SUBSCRIPTION_KEY，请在 .env 配置后再使用 bing 后端"
        )

    endpoint = os.getenv("BING_SEARCH_V7_ENDPOINT", BING_SEARCH_V7_ENDPOINT)
    params = {"q": query, "mkt": BING_LOCALE, "count": count}
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(endpoint, headers=headers, params=params)
        resp.raise_for_status()
        payload = resp.json()

    pages = payload.get("webPages", {}).get("value", [])
    results = normalize(pages[:count], engine="bing")
    return filter_by_domains(results, filter_list)
