import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from llm.extractor import score_leads, _truncate_snippet
from search import search_engine as se


def test_truncate_snippet():
    assert _truncate_snippet("hello", 10) == "hello"
    assert _truncate_snippet("x" * 20, 10) == "x" * 9 + "…"


@pytest.mark.asyncio
async def test_score_leads_batches_and_merges():
    calls = []

    async def fake_batch(anchor, leads, model, snippet_max):
        calls.append(len(leads))
        return {
            leads[0]["url"]: {
                "confidence": 0.9,
                "source_type": "news_media",
                "ownership": "third_party",
                "reason": "ok",
            }
        }

    leads = [{"url": f"https://example.com/{i}", "title": "t", "snippet": "s"} for i in range(5)]
    with patch("llm.extractor._score_leads_batch", side_effect=fake_batch):
        out = await score_leads("Co", {}, leads, "test-model", batch_size=2, max_retries=0)

    assert calls == [2, 2, 1]
    assert len(out) == 3


@pytest.mark.asyncio
async def test_score_new_leads_keeps_none_on_failure():
    merged = {
        "a": {
            "url": "https://a.com",
            "title": "A",
            "snippet": "",
            "confidence": None,
            "source_type": "",
            "ownership": "",
        },
        "b": {
            "url": "https://b.com",
            "title": "B",
            "snippet": "",
            "confidence": None,
            "source_type": "",
            "ownership": "",
        },
    }

    async def scorer(leads):
        return {
            "https://a.com": {
                "confidence": 0.8,
                "source_type": "social",
                "ownership": "first_party",
            }
        }

    scored, pending = await se._score_new_leads(merged, scorer)
    assert scored == 1
    assert pending == 2
    assert merged["a"]["confidence"] == 0.8
    assert merged["b"]["confidence"] is None


def test_rank_domains_skips_unscored():
    merged = {
        "x": {
            "url": "https://forum.example.com/post",
            "title": "x",
            "snippet": "",
            "score": 5.0,
            "confidence": None,
        },
        "y": {
            "url": "https://low.example.com/p",
            "title": "y",
            "snippet": "",
            "score": 1.0,
            "confidence": 0.2,
        },
    }
    picked = se._rank_domains(merged, exclude=set(), limit=5, threshold=0.5)
    assert picked == []


def test_rank_domains_includes_scored_domain():
    merged = {
        "x": {
            "url": "https://forum.example.com/post",
            "title": "x",
            "snippet": "",
            "score": 5.0,
            "confidence": 0.9,
        },
    }
    picked = se._rank_domains(merged, exclude=set(), limit=5, threshold=0.5)
    assert picked == ["forum.example.com"]


def test_rank_domains_never_exceeds_limit_with_marketplaces(monkeypatch):
    """Regression: negative remain used to slice other[:-1] and return dozens."""
    merged = {}
    for i, host in enumerate([f"mp{i}.com" for i in range(5)] + [f"ot{i}.com" for i in range(30)]):
        url = f"https://{host}/p"
        merged[url] = {
            "url": url,
            "title": host,
            "snippet": "",
            "score": 10.0 - i * 0.01,
            "confidence": 0.9,
            "source_type": "marketplace_directory" if host.startswith("mp") else "news_media",
        }

    monkeypatch.setattr(se, "_domain_is_marketplace", lambda merged, d: d.startswith("mp"))
    picked = se._rank_domains(
        merged, exclude=set(), limit=2, threshold=0.5, max_marketplace=3
    )
    assert len(picked) <= 2


def test_bfs_should_abort_on_total_failure():
    merged = {"a": {"url": "https://a.com", "confidence": None}}
    assert se._bfs_should_abort(merged, scored=0, pending=10) is True


def test_bfs_should_abort_on_high_unscored_ratio():
    assert se._bfs_should_abort({}, scored=1, pending=10) is True


def test_bfs_should_not_abort_when_mostly_scored():
    assert se._bfs_should_abort({}, scored=9, pending=10) is False


def test_finalize_drops_unscored_when_filtering():
    merged = {
        "a": {"url": "https://a.com", "score": 1.0, "confidence": None, "engines": set(), "matched_queries": set()},
        "b": {"url": "https://b.com", "score": 1.0, "confidence": 0.8, "engines": set(), "matched_queries": set()},
    }
    out = se._finalize(merged, max_urls=None, threshold=0.5, drop_below_threshold=True)
    assert len(out) == 1
    assert out[0]["url"] == "https://b.com"
