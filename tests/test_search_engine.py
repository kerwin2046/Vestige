from search.search_engine import _merge_into, _finalize


def test_merge_into_records_discovery_path_and_bfs_round():
    merged = {}
    queries = ['"acme" news']
    results = [[{"url": "https://example.com/a", "title": "A", "snippet": "s", "engine": "exa"}]]
    _merge_into(merged, queries, results, bfs_round=0)

    entry = merged["https://example.com/a"]
    assert entry["bfs_round"] == 0
    assert entry["first_query"] == '"acme" news'
    assert len(entry["discovery_paths"]) == 1
    assert "search:discovery" in entry["discovery_paths"][0]
    assert '"acme" news' in entry["discovery_paths"][0]

    focused = [['site:example.com "acme"']]
    focused_results = [[{"url": "https://example.com/a", "title": "A", "snippet": "s", "engine": "serper"}]]
    _merge_into(merged, focused[0], focused_results, bfs_round=2)

    assert entry["bfs_round"] == 0  # 保留最早轮次
    assert len(entry["discovery_paths"]) == 2
    assert any("focused-r2" in p for p in entry["discovery_paths"])

    finalized = _finalize(merged, None, threshold=0.0, drop_below_threshold=False)[0]
    assert finalized["discovery_path"] == entry["discovery_paths"][0]
