from __future__ import annotations

import httpx

from search.web._filter import filter_by_domains

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    from config import SEARXNG_BASE_URL, SEARXNG_ENGINES, SEARXNG_LANGUAGE

    engines = (SEARXNG_ENGINES or "").strip()
    language = (SEARXNG_LANGUAGE or "en").strip() or "en"
    params = {
        "q": query,
        "format": "json",
        "categories": "general",
        "language": language,
        "safesearch": 0,
    }
    if engines:
        params["engines"] = engines
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            SEARXNG_BASE_URL, params=params, headers={"User-Agent": _UA}
        )
    if resp.status_code != 200:
        print(f"⚠️ [searxng] 状态码 {resp.status_code} query={query!r}")
        return []

    data = resp.json()
    results = data.get("results", [])
    if not results:
        dead = data.get("unresponsive_engines") or []
        if dead:
            reasons = ", ".join(f"{e[0]}:{e[1]}" for e in dead)
            print(f"⚠️ [searxng] 0 结果，疑似上游引擎被限流/CAPTCHA → {reasons}")
        return []

    out = []
    for item in results[:count]:
        url = item.get("url")
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": item.get("title", ""),
                "snippet": item.get("content", ""),
                "engine": item.get("engine", "searxng"),
            }
        )
    return filter_by_domains(out, filter_list)
