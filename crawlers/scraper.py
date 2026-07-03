# crawlers/scraper.py
import asyncio
from typing import Any

from crawl4ai import AsyncWebCrawler

from crawlers.extractors import extract_page_structured

# 单页喂给模型的最大字符数，避免上下文过长但又保留足够信息
MAX_CHARS_PER_PAGE = 6000


async def fetch_page_content(url: str, crawler: AsyncWebCrawler) -> dict[str, Any]:
    """
    抓取单个网页并返回结构化结果（失败时返回空字段，不向上抛异常）。
    复用外部传入的 crawler 实例，避免为每个 URL 重启浏览器。
    """
    empty = {
        "markdown": "",
        "links": [],
        "json_ld": [],
        "opengraph": {},
        "metadata": {},
    }
    try:
        result = await crawler.arun(url)
        if not result:
            return empty
        data = extract_page_structured(result, url)
        if data["markdown"]:
            data["markdown"] = data["markdown"][:MAX_CHARS_PER_PAGE]
        return data
    except Exception as e:
        print(f"⚠️ 抓取失败 {url}: {e}")
        return empty


async def fetch_pages_content(urls: list[str]) -> list[dict[str, Any]]:
    """
    并行抓取多个网页，共享同一个 crawler 实例。
    单个页面失败不影响其它页面。
    返回与 urls 等长的 dict 列表，每项含 markdown / links / json_ld / opengraph / metadata。
    """
    async with AsyncWebCrawler() as crawler:
        tasks = [fetch_page_content(url, crawler) for url in urls]
        return await asyncio.gather(*tasks)
