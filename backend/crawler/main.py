# crawler/main.py
"""统一页面抓取结果类型与组装逻辑。"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from extract.html import extract_json_ld, extract_opengraph

_HREF_RE = re.compile(r"""<a[^>]+href=["']([^"']+)["']""", re.I)


def empty_page(url: str = "", crawler_method: str = "") -> dict[str, Any]:
    return {
        "url": url,
        "markdown": "",
        "links": [],
        "json_ld": [],
        "opengraph": {},
        "metadata": {"title": "", "description": ""},
        "crawler_method": crawler_method,
    }


def is_successful(page: dict[str, Any]) -> bool:
    return bool((page.get("markdown") or "").strip())


def links_from_html(html: str, base_url: str = "") -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for href in _HREF_RE.findall(html or ""):
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href) if base_url else href
        if not absolute.startswith(("http://", "https://")):
            continue
        key = absolute.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(absolute)
    return out


def assemble_page(
    url: str,
    *,
    html: str = "",
    markdown: str = "",
    links: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    crawler_method: str = "",
    max_chars: int = 6000,
) -> dict[str, Any]:
    """将各 crawler 后端的原始输出规范化为 pipeline 使用的 dict。"""
    html = html or ""
    meta = dict(metadata or {})
    json_ld = extract_json_ld(html)
    opengraph = extract_opengraph(html)

    if links is None:
        links = links_from_html(html, url) if html else []

    title = meta.get("title") or opengraph.get("title") or ""
    description = meta.get("description") or opengraph.get("description") or ""

    body = (markdown or "").strip()
    if not body and html:
        body = html[:max_chars]

    return {
        "url": url,
        "markdown": body[:max_chars],
        "links": links,
        "json_ld": json_ld,
        "opengraph": opengraph,
        "metadata": {"title": title, "description": description},
        "crawler_method": crawler_method,
    }
