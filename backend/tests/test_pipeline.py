from pipeline import _select_crawl_subset


def _lead(url: str, source_type: str, score: float) -> dict:
    return {
        "url": url,
        "source_type": source_type,
        "weighted_score": score,
    }


def test_select_crawl_subset_covers_each_source_type():
    inventory = [
        _lead("https://a.com/1", "social", 0.9),
        _lead("https://b.com/1", "news_media", 0.8),
        _lead("https://c.com/1", "social", 0.7),
        _lead("https://d.com/1", "other", 0.6),
    ]
    chosen = _select_crawl_subset(inventory, budget=2, per_domain=1)
    types = {r["source_type"] for r in chosen}
    assert "social" in types
    assert "news_media" in types
    assert len(chosen) == 2


def test_select_crawl_subset_respects_domain_limit():
    inventory = [
        _lead("https://a.com/1", "social", 0.9),
        _lead("https://a.com/2", "social", 0.85),
        _lead("https://b.com/1", "news_media", 0.8),
    ]
    chosen = _select_crawl_subset(inventory, budget=10, per_domain=1)
    a_urls = [r["url"] for r in chosen if r["url"].startswith("https://a.com")]
    assert len(a_urls) == 1
