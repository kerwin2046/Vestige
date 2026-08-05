# crawler/camofox.py
"""Camofox REST API 抓取（:9377，适合 JS 重页）。"""
from __future__ import annotations

import json
from typing import Any

import httpx

from .main import assemble_page, empty_page

_EVALUATE_JS = """(() => {
  const links = Array.from(document.querySelectorAll('a[href]'))
    .map(a => a.href)
    .filter(h => h && !h.startsWith('javascript:'))
    .slice(0, 300);
  return JSON.stringify({
    text: document.body?.innerText || '',
    title: document.title || '',
    links
  });
})()"""


def _auth_headers(api_key: str) -> dict[str, str]:
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _tab_id(payload: dict[str, Any]) -> str:
    for key in ("tabId", "id", "tab_id"):
        val = payload.get(key)
        if val:
            return str(val)
    return ""


async def fetch(url: str) -> dict[str, Any]:
    from config import (
        CAMOFOX_API_KEY,
        CAMOFOX_BASE_URL,
        CAMOFOX_TIMEOUT_SEC,
        CAMOFOX_USER_ID,
        MAX_CHARS_PER_PAGE,
    )

    base = CAMOFOX_BASE_URL.rstrip("/")
    timeout = httpx.Timeout(CAMOFOX_TIMEOUT_SEC)
    headers = _auth_headers(CAMOFOX_API_KEY)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            health = await client.get(f"{base}/health")
            if health.status_code != 200:
                return empty_page(url, crawler_method="camofox")
        except Exception:
            return empty_page(url, crawler_method="camofox")

        tab_id = ""
        try:
            create = await client.post(
                f"{base}/tabs",
                json={"userId": CAMOFOX_USER_ID, "url": url},
            )
            create.raise_for_status()
            tab_id = _tab_id(create.json())
            if not tab_id:
                return empty_page(url, crawler_method="camofox")

            evaluate = await client.post(
                f"{base}/tabs/{tab_id}/evaluate",
                headers=headers,
                json={"userId": CAMOFOX_USER_ID, "expression": _EVALUATE_JS},
            )
            evaluate.raise_for_status()
            raw = evaluate.json()
            result = raw.get("result", raw.get("value", ""))
            if isinstance(result, dict):
                data = result
            else:
                data = json.loads(result or "{}")

            html_resp = await client.post(
                f"{base}/tabs/{tab_id}/evaluate",
                headers=headers,
                json={
                    "userId": CAMOFOX_USER_ID,
                    "expression": "document.documentElement.outerHTML",
                },
            )
            html = ""
            if html_resp.is_success:
                html_raw = html_resp.json().get("result", "")
                if isinstance(html_raw, str):
                    html = html_raw

            return assemble_page(
                url,
                html=html,
                markdown=data.get("text", ""),
                links=data.get("links") or None,
                metadata={"title": data.get("title", "")},
                crawler_method="camofox",
                max_chars=MAX_CHARS_PER_PAGE,
            )
        except Exception:
            return empty_page(url, crawler_method="camofox")
        finally:
            if tab_id:
                try:
                    await client.delete(
                        f"{base}/tabs/{tab_id}",
                        params={"userId": CAMOFOX_USER_ID},
                    )
                except Exception:
                    pass
