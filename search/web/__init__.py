"""Pluggable web search providers (open-webui retrieval/web style)."""

from search.web.registry import (
    KNOWN_ENGINES,
    SearchClient,
    get_search_client,
    search_web,
    search_with_fallback,
)

__all__ = [
    "KNOWN_ENGINES",
    "SearchClient",
    "get_search_client",
    "search_web",
    "search_with_fallback",
]
