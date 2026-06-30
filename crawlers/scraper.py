# crawlers/scraper.py
import asyncio
from crawl4ai import AsyncWebCrawler

# 单页喂给模型的最大字符数，避免上下文过长但又保留足够信息
MAX_CHARS_PER_PAGE = 6000


async def fetch_page_content(url: str, crawler: AsyncWebCrawler) -> str:
    """
    抓取单个网页并返回清洗后的 Markdown（失败时返回空串，不向上抛异常）。
    复用外部传入的 crawler 实例，避免为每个 URL 重启浏览器。
    """
    try:
        result = await crawler.arun(url)
        if not result or not result.markdown:
            return ""
        return result.markdown[:MAX_CHARS_PER_PAGE]
    except Exception as e:
        print(f"⚠️ 抓取失败 {url}: {e}")
        return ""


async def fetch_pages_content(urls: list[str]) -> list[str]:
    """
    并行抓取多个网页，共享同一个 crawler 实例。
    单个页面失败不影响其它页面。
    """
    async with AsyncWebCrawler() as crawler:
        tasks = [fetch_page_content(url, crawler) for url in urls]
        return await asyncio.gather(*tasks)
