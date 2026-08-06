"""Tests for incremental footprint source merge."""

from __future__ import annotations

from application.merge_sources import merge_footprint_sources


def test_merge_adds_new_and_keeps_old():
    base = [
        {
            "url": "https://a.example/old",
            "canonical_url": "https://a.example/old",
            "domain": "a.example",
            "confidence": 0.8,
            "title": "Old",
            "snippet": "kept",
            "source_type": "news_media",
            "ownership": "third_party",
        }
    ]
    incoming = [
        {
            "url": "https://b.example/new",
            "canonical_url": "https://b.example/new",
            "domain": "b.example",
            "confidence": 0.7,
            "title": "New",
            "snippet": "added",
            "source_type": "owned",
            "ownership": "first_party",
        }
    ]
    merged, stats = merge_footprint_sources(base, incoming)
    assert stats["added"] == 1
    assert stats["kept"] == 1
    assert stats["updated"] == 0
    assert stats["total"] == 2
    keys = {s["canonical_url"] for s in merged}
    assert keys == {"https://a.example/old", "https://b.example/new"}


def test_merge_updates_same_url_with_higher_confidence():
    base = [
        {
            "url": "https://xometry.com/about",
            "canonical_url": "https://xometry.com/about",
            "domain": "xometry.com",
            "confidence": 0.6,
            "title": "About",
            "snippet": "short",
            "source_type": "owned",
            "ownership": "first_party",
        }
    ]
    incoming = [
        {
            "url": "https://xometry.com/about",
            "canonical_url": "https://xometry.com/about",
            "domain": "xometry.com",
            "confidence": 0.95,
            "title": "About Xometry",
            "snippet": "longer description about the company",
            "source_type": "owned",
            "ownership": "first_party",
        }
    ]
    merged, stats = merge_footprint_sources(base, incoming)
    assert stats["added"] == 0
    assert stats["updated"] == 1
    assert stats["kept"] == 0
    assert len(merged) == 1
    assert merged[0]["confidence"] == 0.95
    assert merged[0]["title"] == "About Xometry"
    assert merged[0]["detail"]["merge"] == "updated"
