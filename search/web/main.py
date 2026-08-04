# search/web/main.py
"""统一搜索命中类型与结果过滤（对齐 open-webui retrieval/web/main.py）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from search.web._filter import filter_by_domains


@dataclass
class SearchHit:
    url: str
    title: str = ""
    snippet: str = ""
    engine: str = ""


def normalize(
    raw: Iterable[Any],
    *,
    engine: str,
    url_keys: Sequence[str] = ("url", "link", "href"),
) -> list[dict]:
    """将各 provider 异构 payload 规范为统一 dict。"""
    out: list[dict] = []
    for item in raw:
        if item is None:
            continue
        if hasattr(item, "link"):
            url = getattr(item, "link", "") or ""
            title = getattr(item, "title", None) or ""
            snippet = getattr(item, "snippet", None) or ""
        elif isinstance(item, dict):
            url = ""
            for key in url_keys:
                val = item.get(key)
                if val:
                    url = val
                    break
            title = item.get("title") or item.get("name") or ""
            snippet = (
                item.get("snippet")
                or item.get("content")
                or item.get("body")
                or item.get("summary")
                or item.get("description")
                or item.get("text")
                or ""
            )
        else:
            continue
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": title,
                "snippet": snippet,
                "engine": engine,
            }
        )
    return out


def hits_to_dicts(hits: list[SearchHit]) -> list[dict]:
    return [
        {
            "url": h.url,
            "title": h.title,
            "snippet": h.snippet,
            "engine": h.engine,
        }
        for h in hits
    ]


def get_filtered_results(
    results: list[dict],
    filter_list: list[str] | None,
) -> list[dict]:
    """按域名白名单过滤（open-webui 兼容命名）。"""
    return filter_by_domains(results, filter_list)
