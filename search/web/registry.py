# search/web/registry.py
"""
可插拔 Web 搜索聚合。

每个引擎一个模块 + PROVIDERS 注册表；上层通过 search_web() / get_search_client() 调用。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from search.throttle import AsyncThrottle
from search.web import (
    bing,
    bocha,
    brave,
    duckduckgo,
    exa,
    exa_mcp,
    google_pse,
    jina,
    kagi,
    mojeek,
    perplexity,
    searxng,
    serper,
    tavily,
)

SearchFn = Callable[..., Awaitable[list[dict]]]

ENGINE_ALIASES: dict[str, str] = {
    "exa-api": "exa",
    "exa_mcp": "exa-mcp",
    "ddg": "duckduckgo",
    "perplexity_search": "perplexity",
    "pse": "google_pse",
    "google": "google_pse",
    "jina_search": "jina",
}

PROVIDERS: dict[str, SearchFn] = {
    "exa": exa.search,
    "exa-mcp": exa_mcp.search,
    "searxng": searxng.search,
    "duckduckgo": duckduckgo.search,
    "brave": brave.search,
    "serper": serper.search,
    "bing": bing.search,
    "tavily": tavily.search,
    "bocha": bocha.search,
    "google_pse": google_pse.search,
    "perplexity": perplexity.search,
    "kagi": kagi.search,
    "jina": jina.search,
    "mojeek": mojeek.search,
}

KNOWN_ENGINES: tuple[str, ...] = tuple(PROVIDERS.keys())


def normalize_engine(name: str) -> str:
    key = (name or "exa").lower().strip()
    return ENGINE_ALIASES.get(key, key)


def _throttle_for(engine: str) -> AsyncThrottle:
    from config import (
        EXA_MAX_CONCURRENCY,
        EXA_MIN_INTERVAL_SEC,
        SEARCH_MAX_CONCURRENCY,
        SEARCH_MIN_INTERVAL_SEC,
        SEARXNG_MAX_CONCURRENCY,
        SEARXNG_MIN_INTERVAL_SEC,
    )

    if engine in ("exa", "exa-mcp"):
        return AsyncThrottle(EXA_MAX_CONCURRENCY, EXA_MIN_INTERVAL_SEC)
    if engine == "searxng":
        return AsyncThrottle(SEARXNG_MAX_CONCURRENCY, SEARXNG_MIN_INTERVAL_SEC)
    return AsyncThrottle(SEARCH_MAX_CONCURRENCY, SEARCH_MIN_INTERVAL_SEC)


async def search_web(
    engine: str,
    query: str,
    count: int = 10,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """调用单个搜索引擎，返回 [{url, title, snippet, engine}]。"""
    name = normalize_engine(engine)
    fn = PROVIDERS.get(name)
    if fn is None:
        raise ValueError(f"未知的检索引擎: {engine!r} (可选: {', '.join(KNOWN_ENGINES)})")

    throttle = _throttle_for(name)
    async with throttle:
        try:
            return await fn(query=query, count=count, filter_list=filter_list)
        except Exception as e:
            print(f"⚠️ [{name}] 检索失败 query={query!r}: {e}")
            return []


async def search_with_fallback(
    query: str,
    *,
    primary: str,
    fallbacks: list[str] | None = None,
    count: int = 10,
    filter_list: list[str] | None = None,
) -> list[dict]:
    """主引擎失败或空结果时，依次尝试备用引擎。"""
    chain: list[str] = []
    for name in [primary, *(fallbacks or [])]:
        norm = normalize_engine(name)
        if norm not in chain:
            chain.append(norm)

    for name in chain:
        results = await search_web(name, query, count, filter_list=filter_list)
        if results:
            return results
    return []


class SearchClient:
    """兼容 search_engine.py 的 backend 接口：.name + .search()。"""

    def __init__(self, primary: str, fallbacks: list[str] | None = None):
        self.primary = normalize_engine(primary)
        self.fallbacks = [
            normalize_engine(n)
            for n in (fallbacks or [])
            if normalize_engine(n) != self.primary
        ]
        # 去重保序
        seen = {self.primary}
        unique_fallbacks: list[str] = []
        for n in self.fallbacks:
            if n not in seen:
                seen.add(n)
                unique_fallbacks.append(n)
        self.fallbacks = unique_fallbacks
        if self.fallbacks:
            self.name = "/".join([self.primary, *self.fallbacks])
        else:
            self.name = self.primary

    async def search(self, query: str, max_results: int) -> list[dict]:
        return await search_with_fallback(
            query,
            primary=self.primary,
            fallbacks=self.fallbacks,
            count=max_results,
        )


def get_search_client(
    primary: str | None = None,
    fallbacks: list[str] | None = None,
) -> SearchClient:
    from config import SEARCH_BACKEND, SEARCH_FALLBACK_BACKENDS

    return SearchClient(
        primary=primary or SEARCH_BACKEND,
        fallbacks=fallbacks if fallbacks is not None else list(SEARCH_FALLBACK_BACKENDS or []),
    )


# 向后兼容旧名
get_search_backend = get_search_client
