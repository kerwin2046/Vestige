from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains
from search.web.main import normalize

_DEFAULT_BASE_URL = "https://s.jina.ai/"


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """Jina Search API（s.jina.ai）。"""
    import os

    api_key = os.getenv("JINA_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 JINA_API_KEY，请在 .env 配置后再使用 jina 后端")

    base_url = os.getenv("JINA_SEARCH_BASE_URL", _DEFAULT_BASE_URL).rstrip("/") + "/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}",
        "X-Retain-Images": "none",
    }
    body = {"q": query, "count": min(count, 10)}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(base_url, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    raw = payload.get("data", [])
    results = normalize(raw[:count], engine="jina")
    return filter_by_domains(results, filter_list)
