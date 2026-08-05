# search/backends.py
"""
向后兼容层 — 新代码请使用 search.web.registry。

Phase 1 已将可插拔搜索迁入 search/web/（Open WebUI 风格 registry）。
"""
from search.throttle import AsyncThrottle
from search.web.exa_mcp import build_mcporter_exa_args, parse_mcporter_exa_response
from search.web.registry import SearchClient, get_search_backend, get_search_client

# 旧测试/导入使用的别名
_build_mcporter_exa_args = build_mcporter_exa_args
_parse_mcporter_exa_response = parse_mcporter_exa_response


class ExaMcpBackend:
    """已废弃：请使用 search_web('exa-mcp', query)。"""

    name = "exa-mcp"

    def __init__(self, throttle: AsyncThrottle, mcporter_bin: str = "mcporter", timeout_sec: float = 60.0):
        self._client = SearchClient("exa-mcp")

    async def search(self, query: str, max_results: int) -> list[dict]:
        return await self._client.search(query, max_results)


__all__ = [
    "AsyncThrottle",
    "ExaMcpBackend",
    "SearchClient",
    "_build_mcporter_exa_args",
    "_parse_mcporter_exa_response",
    "get_search_backend",
    "get_search_client",
]
