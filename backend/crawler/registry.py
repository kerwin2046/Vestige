# crawler/registry.py
"""
可插拔页面抓取 + 反爬升级链。

默认链: crawl4ai → camofox → cloak
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from . import camofox, cloak, crawl4ai
from .main import empty_page, is_successful

CrawlFn = Callable[[str], Awaitable[dict[str, Any]]]

ENGINE_ALIASES: dict[str, str] = {
    "c4ai": "crawl4ai",
    "crawl": "crawl4ai",
}

KNOWN_CRAWLERS: tuple[str, ...] = ("crawl4ai", "camofox", "cloak")


def normalize_crawler(name: str) -> str:
    key = (name or "crawl4ai").lower().strip()
    return ENGINE_ALIASES.get(key, key)


def _provider_fn(name: str) -> CrawlFn | None:
    if name == "crawl4ai":
        return crawl4ai.fetch_one
    if name == "camofox":
        return camofox.fetch
    if name == "cloak":
        return cloak.fetch
    return None


def _resolve_chain() -> list[str]:
    from config import CRAWLER_CHAIN, CRAWLER_ESCALATION

    if not CRAWLER_ESCALATION:
        return ["crawl4ai"]

    chain: list[str] = []
    for name in CRAWLER_CHAIN:
        key = normalize_crawler(name)
        if key in KNOWN_CRAWLERS and key not in chain:
            chain.append(key)
    return chain or ["crawl4ai"]


async def _crawl4ai_batch(urls: list[str], indices: list[int]) -> list[tuple[int, dict[str, Any]]]:
    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as crawler:
        out: list[tuple[int, dict[str, Any]]] = []
        for i in indices:
            page = await crawl4ai.fetch_one(urls[i], crawler=crawler)
            out.append((i, page))
        return out


async def crawl_url(url: str) -> dict[str, Any]:
    """按配置链依次尝试，直到某后端返回非空 markdown。"""
    chain = _resolve_chain()
    page = empty_page(url)

    for i, name in enumerate(chain):
        if name == "crawl4ai":
            page = await crawl4ai.fetch_one(url)
        else:
            fn = _provider_fn(name)
            if fn is None:
                continue
            page = await fn(url)

        if is_successful(page):
            return page

        if i == len(chain) - 1:
            return page

    return page


async def crawl_pages(urls: list[str]) -> list[dict[str, Any]]:
    """批量抓取：每个后端只处理上一轮失败的 URL（共享 crawl4ai 浏览器）。"""
    if not urls:
        return []

    chain = _resolve_chain()
    results: list[dict[str, Any]] = [empty_page(u) for u in urls]
    pending = list(range(len(urls)))

    for name in chain:
        if not pending:
            break

        if name == "crawl4ai":
            print(f"   [crawler] crawl4ai → {len(pending)} URL(s)")
            still_pending: list[int] = []
            for i, page in await _crawl4ai_batch(urls, pending):
                results[i] = page
                if not is_successful(page):
                    still_pending.append(i)
            pending = still_pending
            continue

        fn = _provider_fn(name)
        if fn is None:
            continue

        print(f"   [crawler] {name} → {len(pending)} URL(s) (升级)")
        still_pending = []
        for i in pending:
            page = await fn(urls[i])
            results[i] = page
            if not is_successful(page):
                still_pending.append(i)
        pending = still_pending

    return results
