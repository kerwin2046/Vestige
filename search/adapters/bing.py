from __future__ import annotations

import httpx

from search.adapters._filter import filter_by_domains
from search.adapters._types import normalize

DEFAULT_BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


async def search(
    subscription_key: str,
    query: str,
    count: int,
    endpoint: str = DEFAULT_BING_ENDPOINT,
    locale: str = "en-US",
    filter_list: list[str] | None = None,
) -> list[dict]:
    params = {"q": query, "mkt": locale, "count": count}
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(endpoint, headers=headers, params=params)
        resp.raise_for_status()
        payload = resp.json()

    pages = payload.get("webPages", {}).get("value", [])
    results = normalize(pages[:count], engine="bing")
    return filter_by_domains(results, filter_list)
