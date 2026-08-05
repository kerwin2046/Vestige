from __future__ import annotations

import asyncio
import re

from search.web._filter import filter_by_domains

_SITE_RE = re.compile(r"site:([^\s\"')]+)", re.I)


def exa_query_params(query: str) -> tuple[str, list[str]]:
    """把 `site:domain` 语法转为 Exa 的 include_domains + 清理后的 query。"""
    domains = [d.lower().lstrip(".") for d in _SITE_RE.findall(query)]
    clean = _SITE_RE.sub("", query)
    clean = re.sub(r"\s+OR\s+", " ", clean, flags=re.I)
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    return clean or query, domains


def _exa_snippet(item) -> str:
    highlights = getattr(item, "highlights", None) or []
    if highlights:
        return highlights[0] if isinstance(highlights[0], str) else str(highlights[0])
    summary = getattr(item, "summary", None) or ""
    if summary:
        return summary
    text = getattr(item, "text", None) or ""
    return text[:500] if text else ""


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    import os

    from config import EXA_SEARCH_TYPE

    api_key = os.getenv("EXA_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 EXA_API_KEY，请在 .env 配置后再使用 exa 后端")

    clean_query, include_domains = exa_query_params(query)

    def _sync():
        from exa_py import Exa

        exa = Exa(api_key=api_key)
        kwargs: dict = {
            "type": EXA_SEARCH_TYPE,
            "num_results": min(max(count, 1), 100),
            "contents": {"highlights": True},
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        return exa.search(clean_query, **kwargs)

    response = await asyncio.to_thread(_sync)
    out = []
    for item in response.results or []:
        url = getattr(item, "url", None)
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": getattr(item, "title", "") or "",
                "snippet": _exa_snippet(item),
                "engine": "exa",
            }
        )
    return filter_by_domains(out, filter_list)
