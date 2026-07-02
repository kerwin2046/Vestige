import json
from unittest.mock import patch

import pytest

from search.backends import (
    ExaMcpBackend,
    AsyncThrottle,
    _build_mcporter_exa_args,
    _parse_mcporter_exa_response,
    get_search_backend,
)


def test_build_mcporter_exa_args_site_syntax():
    args = _build_mcporter_exa_args('site:reddit.com "冠盛" review', 5)
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
    out = _parse_mcporter_exa_response(json.dumps(payload))
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
    out = _parse_mcporter_exa_response(json.dumps(payload))
    assert out[0]["url"] == "https://example.com/b"
    assert out[0]["snippet"] == "body b"


def test_parse_mcporter_exa_response_mcp_text_content():
    inner = {"results": [{"url": "https://example.com/c", "summary": "sum c"}]}
    payload = {"content": [{"type": "text", "text": json.dumps(inner)}]}
    out = _parse_mcporter_exa_response(json.dumps(payload))
    assert out[0]["url"] == "https://example.com/c"
    assert out[0]["snippet"] == "sum c"


def test_parse_mcporter_exa_response_error_envelope():
    payload = {"server": "exa", "tool": "web_search_exa", "issue": "offline"}
    with pytest.raises(RuntimeError, match="offline"):
        _parse_mcporter_exa_response(json.dumps(payload))


@pytest.mark.asyncio
async def test_exa_mcp_backend_invokes_mcporter():
    backend = ExaMcpBackend(AsyncThrottle(1, 0), mcporter_bin="mcporter", timeout_sec=5)
    fake_stdout = json.dumps(
        {"results": [{"url": "https://example.com/x", "title": "X", "text": "hello"}]}
    )

    with patch("search.backends.shutil.which", return_value="/usr/bin/mcporter"), patch(
        "asyncio.to_thread", return_value=fake_stdout
    ):
        out = await backend.search('"test company"', 3)

    assert len(out) == 1
    assert out[0]["engine"] == "exa-mcp"


def test_get_search_backend_exa_mcp(monkeypatch):
    monkeypatch.setattr("config.SEARCH_BACKEND", "exa-mcp", raising=False)
    backend = get_search_backend()
    assert backend.name == "exa-mcp"
