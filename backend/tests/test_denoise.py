from search.denoise import collapse_domain_redundancy, filter_directory_noise, is_owned_domain


def _lead(url: str, **kwargs) -> dict:
    return {
        "url": url,
        "title": kwargs.get("title", ""),
        "snippet": kwargs.get("snippet", ""),
        "source_type": kwargs.get("source_type", "other"),
        "ownership": kwargs.get("ownership", "third_party"),
        "confidence": kwargs.get("confidence", 0.8),
        "score": kwargs.get("score", 1.0),
        "weighted_score": kwargs.get("weighted_score", 0.8),
    }


def test_collapse_aggregator_domain_keeps_top_two():
    inventory = [
        _lead(f"https://rocketreach.co/person/{i}", title="Fictiv contact", weighted_score=i / 10)
        for i in range(5)
    ]
    anchor = {"official_domain": "fictiv.com"}
    kept, removed = collapse_domain_redundancy(inventory, anchor)
    assert len(kept) == 2
    assert removed == 3
    assert kept[0]["weighted_score"] == 0.4


def test_collapse_official_domain_keeps_one_homepage():
    inventory = [
        _lead("https://www.rapiddirect.com/blog/post-1", ownership="first_party", weighted_score=0.9),
        _lead("https://www.rapiddirect.com/contact/", ownership="first_party", weighted_score=0.85),
        _lead("https://www.rapiddirect.com/", ownership="first_party", weighted_score=0.8),
        _lead("https://www.rapiddirect.com/about-rapiddirect/", ownership="first_party", weighted_score=0.7),
    ]
    anchor = {"official_domain": "rapiddirect.com"}
    kept, removed = collapse_domain_redundancy(inventory, anchor)
    assert len(kept) == 1
    assert removed == 3
    assert kept[0]["url"] == "https://www.rapiddirect.com/"


def test_is_owned_domain_by_first_party_ratio():
    leads = [
        _lead("https://example.com/a", ownership="first_party"),
        _lead("https://example.com/b", ownership="first_party"),
        _lead("https://example.com/c", ownership="first_party"),
        _lead("https://example.com/d", ownership="third_party"),
    ]
    assert is_owned_domain("example.com", leads, {})


def test_filter_directory_noise_removes_irrelevant_marketplace():
    anchor = {"name": "Fictiv", "official_domain": "fictiv.com", "aliases": []}
    inventory = [
        _lead("https://rocketreach.co/x", title="Unrelated supplier", source_type="marketplace_directory"),
        _lead("https://rocketreach.co/y", title="Fictiv CEO email", source_type="marketplace_directory"),
    ]
    kept, removed = filter_directory_noise(inventory, "Fictiv", anchor)
    assert removed == 1
    assert len(kept) == 1
    assert "Fictiv" in kept[0]["title"]
