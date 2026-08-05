# crawler/crawl4ai.py
"""Crawl4AI 标准 Playwright 抓取（链首，无反爬能力）。"""
from __future__ import annotations

from typing import Any

from extract.html import extract_page_structured

from .main import empty_page


async def fetch_one(url: str, crawler: Any | None = None) -> dict[str, Any]:
    """抓取单页；可传入共享 crawler 实例以复用浏览器。"""
    if crawler is not None:
        return await _fetch_with_crawler(url, crawler)

    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as owned:
        return await _fetch_with_crawler(url, owned)


async def _fetch_with_crawler(url: str, crawler: Any) -> dict[str, Any]:
    try:
        result = await crawler.arun(url=url)
        if not result.success:
            return empty_page(url, crawler_method="crawl4ai")

        page = extract_page_structured(result, url)
        page["url"] = url
        page["crawler_method"] = "crawl4ai"
        return page
    except Exception:
        return empty_page(url, crawler_method="crawl4ai")
