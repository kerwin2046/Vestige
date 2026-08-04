# extract/html.py
"""从 HTML / Crawl4AI 结果中抽取链接、JSON-LD、OpenGraph 等结构化字段。"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

_JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
_OG_META_RE = re.compile(
    r'<meta[^>]+property=["\']og:([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.I,
)


def extract_json_ld(html: str) -> list[dict]:
    out: list[dict] = []
    for match in _JSON_LD_RE.finditer(html or ""):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            out.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            out.append(data)
    return out


def extract_opengraph(html: str) -> dict[str, str]:
    og: dict[str, str] = {}
    for prop, content in _OG_META_RE.findall(html or ""):
        if content:
            og[prop.lower()] = content
    return og


def _link_href(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return (item.get("href") or item.get("url") or "").strip()
    return ""


def extract_links(crawl_result: Any, base_url: str = "") -> list[str]:
    """从 Crawl4AI 结果对象提取去重后的绝对 URL 列表。"""
    raw = getattr(crawl_result, "links", None)
    candidates: list[str] = []

    if isinstance(raw, dict):
        for key in ("internal", "external", "urls", "links"):
            val = raw.get(key)
            if isinstance(val, list):
                candidates.extend(_link_href(x) for x in val)
    elif isinstance(raw, list):
        candidates.extend(_link_href(x) for x in raw)

    metadata = getattr(crawl_result, "metadata", None) or {}
    if isinstance(metadata, dict):
        for key in ("links", "internal_links", "external_links"):
            val = metadata.get(key)
            if isinstance(val, list):
                candidates.extend(_link_href(x) for x in val)

    return _dedupe_absolute_urls(candidates, base_url)


def _dedupe_absolute_urls(urls: list[str], base_url: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for href in urls:
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


def extract_page_structured(crawl_result: Any, url: str) -> dict:
    """汇总单页结构化抽取结果，供 pipeline / Excel 使用。"""
    markdown = ""
    if crawl_result is not None:
        markdown = (getattr(crawl_result, "markdown", None) or "")[:6000]

    html = getattr(crawl_result, "html", None) or ""
    metadata = getattr(crawl_result, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    json_ld = extract_json_ld(html)
    opengraph = extract_opengraph(html)
    links = extract_links(crawl_result, base_url=url)

    title = metadata.get("title") or opengraph.get("title") or ""
    description = metadata.get("description") or opengraph.get("description") or ""

    return {
        "markdown": markdown,
        "links": links,
        "json_ld": json_ld,
        "opengraph": opengraph,
        "metadata": {
            "title": title,
            "description": description,
        },
    }
