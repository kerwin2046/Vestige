from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

SERPER_ENDPOINT = "https://google.serper.dev/search"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    import os

    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 SERPER_API_KEY，请在 .env 配置后再使用 serper 后端")

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(SERPER_ENDPOINT, headers=headers, json={"q": query})
        resp.raise_for_status()
        payload = resp.json()

    organic = sorted(payload.get("organic", []), key=lambda item: item.get("position", 0))
    results = normalize(organic[:count], engine="serper")
    return filter_by_domains(results, filter_list)
