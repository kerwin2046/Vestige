import json
from unittest.mock import patch

import pytest

from search.backends import get_search_backend
from search.throttle import AsyncThrottle
from search.web.exa_mcp import build_mcporter_exa_args, parse_mcporter_exa_response
from search.web.registry import SearchClient, get_search_client, normalize_engine


def test_build_mcporter_exa_args_site_syntax():
    args = build_mcporter_exa_args('site:reddit.com "冠盛" review', 5)
    assert args["query"] == '"冠盛" review'
    assert args["numResults"] == 5
    assert args["includeDomains"] == ["reddit.com"]


def test_parse_mcporter_exa_response_direct_results():
    payload = {
        "results": [
            {
                "url": "https://example.com/a",
                "title": "A",
                "highlights": ["snippet a"],
            }
        ]
    }
    out = parse_mcporter_exa_response(json.dumps(payload))
    assert len(out) == 1
    assert out[0]["url"] == "https://example.com/a"
    assert out[0]["snippet"] == "snippet a"
    assert out[0]["engine"] == "exa-mcp"


def test_parse_mcporter_exa_response_structured_content():
    payload = {
        "structuredContent": {
            "results": [
                {"url": "https://example.com/b", "title": "B", "text": "body b"}
            ]
        }
    }
    out = parse_mcporter_exa_response(json.dumps(payload))
    assert out[0]["url"] == "https://example.com/b"
    assert out[0]["snippet"] == "body b"


def test_parse_mcporter_exa_response_mcp_text_content():
    inner = {"results": [{"url": "https://example.com/c", "summary": "sum c"}]}
    payload = {"content": [{"type": "text", "text": json.dumps(inner)}]}
    out = parse_mcporter_exa_response(json.dumps(payload))
    assert out[0]["url"] == "https://example.com/c"
    assert out[0]["snippet"] == "sum c"


def test_parse_mcporter_exa_response_error_envelope():
    payload = {"server": "exa", "tool": "web_search_exa", "issue": "offline"}
    with pytest.raises(RuntimeError, match="offline"):
        parse_mcporter_exa_response(json.dumps(payload))


@pytest.mark.asyncio
async def test_exa_mcp_search_invokes_mcporter():
    client = SearchClient("exa-mcp")
    fake_stdout = json.dumps(
        {"results": [{"url": "https://example.com/x", "title": "X", "text": "hello"}]}
    )

    with patch("search.web.exa_mcp.shutil.which", return_value="/usr/bin/mcporter"), patch(
        "asyncio.to_thread", return_value=fake_stdout
    ):
        out = await client.search('"test company"', 3)

    assert len(out) == 1
    assert out[0]["engine"] == "exa-mcp"


def test_get_search_client_exa_mcp(monkeypatch):
    monkeypatch.setattr("config.SEARCH_BACKEND", "exa-mcp", raising=False)
    client = get_search_client()
    assert client.name == "exa-mcp"


def test_get_search_backend_alias():
    assert get_search_backend is get_search_client


def test_normalize_engine_aliases():
    assert normalize_engine("ddg") == "duckduckgo"
    assert normalize_engine("exa-api") == "exa"
    assert normalize_engine("exa_mcp") == "exa-mcp"
