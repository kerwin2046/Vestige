from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


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
    """Map heterogeneous provider payloads to Vestige's unified search result dict."""
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
