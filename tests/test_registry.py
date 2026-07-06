import pytest

from search.web.main import normalize
from search.web.registry import KNOWN_ENGINES, SearchClient, normalize_engine


def test_normalize_dict_results():
    raw = [{"url": "https://a.com", "title": "A", "snippet": "s"}]
    out = normalize(raw, engine="test")
    assert out[0]["engine"] == "test"
    assert out[0]["url"] == "https://a.com"


def test_known_engines_includes_core_providers():
    for name in (
        "exa",
        "searxng",
        "serper",
        "bing",
        "brave",
        "duckduckgo",
        "tavily",
        "bocha",
        "google_pse",
        "perplexity",
        "kagi",
        "jina",
        "mojeek",
    ):
        assert name in KNOWN_ENGINES


def test_normalize_engine_new_aliases():
    assert normalize_engine("perplexity_search") == "perplexity"
    assert normalize_engine("pse") == "google_pse"
    assert normalize_engine("jina_search") == "jina"


@pytest.mark.asyncio
async def test_google_pse_pagination(monkeypatch):
    import search.web.google_pse as gp

    calls: list[dict] = []

    class FakeResp:
        def __init__(self, items):
            self._items = items

        def raise_for_status(self):
            return None

        def json(self):
            return {"items": self._items}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers=None, params=None):
            calls.append(params)
            start = int(params["start"])
            if start == 1:
                return FakeResp(
                    [{"link": f"https://a{i}.com", "title": f"A{i}", "snippet": "s"} for i in range(10)]
                )
            return FakeResp(
                [{"link": f"https://b{i}.com", "title": f"B{i}", "snippet": "s"} for i in range(5)]
            )

    monkeypatch.setenv("GOOGLE_PSE_API_KEY", "key")
    monkeypatch.setenv("GOOGLE_PSE_ENGINE_ID", "cx")
    monkeypatch.setattr(gp.httpx, "AsyncClient", lambda **kw: FakeClient())

    out = await gp.search("test", 15)
    assert len(out) == 15
    assert calls[0]["start"] == "1"
    assert calls[1]["start"] == "11"


def test_search_client_fallback_name():
    client = SearchClient("serper", ["exa", "searxng"])
    assert client.name == "serper/exa/searxng"


@pytest.mark.asyncio
async def test_search_with_fallback_uses_second_engine(monkeypatch):
    calls: list[str] = []

    async def fake_search_web(engine, query, count=10, filter_list=None):
        calls.append(engine)
        if engine == "exa":
            return []
        return [{"url": "https://ok.com", "title": "OK", "snippet": "", "engine": engine}]

    monkeypatch.setattr("search.web.registry.search_web", fake_search_web)
    client = SearchClient("exa", ["serper"])
    out = await client.search("test", 5)
    assert out[0]["url"] == "https://ok.com"
    assert calls == ["exa", "serper"]


def test_normalize_engine_dedupes_unknown():
    assert normalize_engine("unknown-xyz") == "unknown-xyz"
