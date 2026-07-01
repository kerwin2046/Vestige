# search/backends.py
"""
可插拔检索后端 (Pluggable Search Backends)。

上层 BFS / 消歧逻辑只依赖统一接口 SearchBackend.search()，
因此可以在 SearXNG / DDG / Brave / Exa API 之间自由切换而不动上层代码。

所有后端共享一个限流器(AsyncThrottle)：并发上限 + 请求最小间隔，
用来避免“单 IP 高频”触发上游引擎的限流/CAPTCHA。
"""
import asyncio
import os
import re
from abc import ABC, abstractmethod

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class AsyncThrottle:
    """并发上限 + 请求最小间隔的异步限流器。"""

    def __init__(self, max_concurrency: int, min_interval: float):
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._min_interval = max(0.0, min_interval)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self):
        await self._sem.acquire()
        if self._min_interval > 0:
            async with self._lock:
                loop = asyncio.get_event_loop()
                wait = self._min_interval - (loop.time() - self._last)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = loop.time()
        return self

    async def __aexit__(self, *exc):
        self._sem.release()


class SearchBackend(ABC):
    """检索后端统一接口。子类只需实现 _search_impl()。"""

    name = "base"

    def __init__(self, throttle: AsyncThrottle):
        self.throttle = throttle

    async def search(self, query: str, max_results: int) -> list[dict]:
        """返回结构化结果: [{"url","title","snippet","engine"}]，失败返回 []。"""
        async with self.throttle:
            try:
                return await self._search_impl(query, max_results)
            except Exception as e:
                print(f"⚠️ [{self.name}] 检索失败 query={query!r}: {e}")
                return []

    @abstractmethod
    async def _search_impl(self, query: str, max_results: int) -> list[dict]:
        ...


class SearxngBackend(SearchBackend):
    """本地/自建 SearXNG 元搜索。免费、自用，但受上游引擎限流影响。"""

    name = "searxng"

    def __init__(self, throttle: AsyncThrottle, base_url: str, engines: str = ""):
        super().__init__(throttle)
        self.base_url = base_url
        self.engines = (engines or "").strip()

    async def _search_impl(self, query: str, max_results: int) -> list[dict]:
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": "all",
            "safesearch": 0,
        }
        if self.engines:
            params["engines"] = self.engines
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self.base_url, params=params, headers={"User-Agent": _UA})
        if resp.status_code != 200:
            print(f"⚠️ [searxng] 状态码 {resp.status_code} query={query!r}")
            return []

        data = resp.json()
        results = data.get("results", [])
        if not results:
            # 关键友好报错：区分“真没结果” vs “引擎被限流/CAPTCHA”
            dead = data.get("unresponsive_engines") or []
            if dead:
                reasons = ", ".join(f"{e[0]}:{e[1]}" for e in dead)
                print(f"⚠️ [searxng] 0 结果，疑似上游引擎被限流/CAPTCHA → {reasons}")
            return []

        out = []
        for item in results[:max_results]:
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
        return out


class DdgsBackend(SearchBackend):
    """DuckDuckGo (ddgs 库)。同步库，丢到线程池执行。"""

    name = "ddg"

    async def _search_impl(self, query: str, max_results: int) -> list[dict]:
        from ddgs import DDGS  # 延迟导入，未选用时不强制依赖

        def _sync() -> list[dict]:
            with DDGS() as d:
                try:
                    return d.text(query, max_results=max_results, safesearch="off")
                except Exception as e:
                    # ddgs 在“零结果”时会抛异常，这属于正常情况，按空结果处理
                    if "no results" in str(e).lower():
                        return []
                    raise

        raw = await asyncio.to_thread(_sync)
        out = []
        for item in raw or []:
            url = item.get("href")
            if not url:
                continue
            out.append(
                {
                    "url": url,
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                    "engine": "duckduckgo",
                }
            )
        return out


class BraveApiBackend(SearchBackend):
    """Brave Search API：带 key 的稳定 JSON 结果，不 CAPTCHA。适合上量/上生产。"""

    name = "brave"
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, throttle: AsyncThrottle, api_key: str):
        super().__init__(throttle)
        self.api_key = api_key

    async def _search_impl(self, query: str, max_results: int) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("缺少 BRAVE_API_KEY，请在 .env 配置后再使用 brave 后端")
        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        params = {"q": query, "count": max_results}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.ENDPOINT, params=params, headers=headers)
        if resp.status_code != 200:
            print(f"⚠️ [brave] 状态码 {resp.status_code} query={query!r}: {resp.text[:200]}")
            return []
        results = (resp.json().get("web", {}) or {}).get("results", [])
        out = []
        for item in results[:max_results]:
            url = item.get("url")
            if not url:
                continue
            out.append(
                {
                    "url": url,
                    "title": item.get("title", ""),
                    "snippet": item.get("description", ""),
                    "engine": "brave",
                }
            )
        return out


_SITE_RE = re.compile(r"site:([^\s\"')]+)", re.I)


def _exa_query_params(query: str) -> tuple[str, list[str]]:
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


class ExaBackend(SearchBackend):
    """
    Exa Search API — 神经搜索，无 CAPTCHA。
    文档: https://docs.exa.ai/reference/search-api-guide-for-coding-agents
    """

    name = "exa"

    def __init__(self, throttle: AsyncThrottle, api_key: str, search_type: str = "auto"):
        super().__init__(throttle)
        self.api_key = api_key
        self.search_type = search_type

    async def _search_impl(self, query: str, max_results: int) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("缺少 EXA_API_KEY，请在 .env 配置后再使用 exa 后端")

        clean_query, include_domains = _exa_query_params(query)

        def _sync():
            from exa_py import Exa

            exa = Exa(api_key=self.api_key)
            kwargs: dict = {
                "type": self.search_type,
                "num_results": min(max(max_results, 1), 100),
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
        return out


def get_search_backend() -> SearchBackend:
    """根据 config.SEARCH_BACKEND 构造后端实例（每次检索任务用一个，限流器随之共享）。"""
    from config import (
        SEARCH_BACKEND,
        SEARXNG_BASE_URL,
        SEARXNG_ENGINES,
        SEARXNG_MAX_CONCURRENCY,
        SEARXNG_MIN_INTERVAL_SEC,
        EXA_SEARCH_TYPE,
        EXA_MAX_CONCURRENCY,
        EXA_MIN_INTERVAL_SEC,
        SEARCH_MAX_CONCURRENCY,
        SEARCH_MIN_INTERVAL_SEC,
    )

    backend = (SEARCH_BACKEND or "searxng").lower()

    if backend == "searxng":
        throttle = AsyncThrottle(SEARXNG_MAX_CONCURRENCY, SEARXNG_MIN_INTERVAL_SEC)
        return SearxngBackend(throttle, SEARXNG_BASE_URL, SEARXNG_ENGINES)

    if backend == "exa":
        throttle = AsyncThrottle(EXA_MAX_CONCURRENCY, EXA_MIN_INTERVAL_SEC)
        return ExaBackend(throttle, os.getenv("EXA_API_KEY", ""), EXA_SEARCH_TYPE)

    throttle = AsyncThrottle(SEARCH_MAX_CONCURRENCY, SEARCH_MIN_INTERVAL_SEC)
    if backend == "ddg":
        return DdgsBackend(throttle)
    if backend == "brave":
        return BraveApiBackend(throttle, os.getenv("BRAVE_API_KEY", ""))
    raise ValueError(f"未知的 SEARCH_BACKEND: {SEARCH_BACKEND!r} (可选: searxng/ddg/brave/exa)")
