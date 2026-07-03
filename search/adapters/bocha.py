from __future__ import annotations

import httpx

from search.adapters._filter import filter_by_domains
from search.adapters._types import normalize

BOCHA_ENDPOINT = "https://api.bochaai.com/v1/web-search"


def _parse_bocha_payload(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    web_pages = data.get("webPages") or {}
    return list(web_pages.get("value") or [])


async def search(
    api_key: str,
    query: str,
    count: int,
    filter_list: list[str] | None = None,
) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "query": query,
        "summary": True,
        "freshness": "noLimit",
        "count": count,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(BOCHA_ENDPOINT, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    raw = _parse_bocha_payload(payload)
    results = normalize(raw[:count], engine="bocha")
    return filter_by_domains(results, filter_list)
