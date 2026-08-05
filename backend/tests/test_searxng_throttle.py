"""Shared throttle must actually bound concurrent SearXNG fan-out."""

from __future__ import annotations

import asyncio
import time

import pytest

from search.web import registry


@pytest.mark.asyncio
async def test_searxng_throttle_is_shared_across_gather(monkeypatch):
    registry.reset_throttles()
    monkeypatch.setattr("config.SEARXNG_MAX_CONCURRENCY", 2, raising=False)
    monkeypatch.setattr("config.SEARXNG_MIN_INTERVAL_SEC", 0.0, raising=False)

    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def fake_search(*, query: str, count: int, filter_list=None):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return [{"url": f"https://example.com/{query}", "title": query, "snippet": "", "engine": "searxng"}]

    monkeypatch.setitem(registry.PROVIDERS, "searxng", fake_search)

    await asyncio.gather(
        *[registry.search_web("searxng", f"q{i}", 3) for i in range(8)]
    )

    assert peak <= 2
    assert registry._throttle_for("searxng") is registry._throttle_for("searxng")
    registry.reset_throttles()


@pytest.mark.asyncio
async def test_searxng_min_interval_is_enforced(monkeypatch):
    registry.reset_throttles()
    monkeypatch.setattr("config.SEARXNG_MAX_CONCURRENCY", 1, raising=False)
    monkeypatch.setattr("config.SEARXNG_MIN_INTERVAL_SEC", 0.15, raising=False)

    async def fake_search(*, query: str, count: int, filter_list=None):
        return []

    monkeypatch.setitem(registry.PROVIDERS, "searxng", fake_search)

    t0 = time.monotonic()
    await registry.search_web("searxng", "a", 1)
    await registry.search_web("searxng", "b", 1)
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.14
    registry.reset_throttles()
