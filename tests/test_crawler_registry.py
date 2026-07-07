import json

import pytest

from crawler.main import assemble_page, empty_page, is_successful, links_from_html
from crawler.registry import KNOWN_CRAWLERS, crawl_pages, crawl_url, normalize_crawler


def test_normalize_crawler_aliases():
    assert normalize_crawler("c4ai") == "crawl4ai"
    assert normalize_crawler("cloak") == "cloak"


def test_known_crawlers():
    assert "crawl4ai" in KNOWN_CRAWLERS
    assert "camofox" in KNOWN_CRAWLERS
    assert "cloak" in KNOWN_CRAWLERS


def test_is_successful_requires_markdown():
    assert not is_successful(empty_page())
    assert is_successful({"markdown": "hello"})


def test_links_from_html_resolves_relative():
    html = '<a href="/about">x</a><a href="https://b.com">y</a>'
    links = links_from_html(html, "https://a.com/page")
    assert "https://a.com/about" in links
    assert "https://b.com" in links


def test_assemble_page_extracts_json_ld():
    html = """
    <script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>
    <a href="https://acme.com/contact">Contact</a>
    """
    page = assemble_page("https://acme.com", html=html, markdown="Acme Corp", crawler_method="cloak")
    assert page["crawler_method"] == "cloak"
    assert page["json_ld"][0]["name"] == "Acme"
    assert "https://acme.com/contact" in page["links"]


@pytest.mark.asyncio
async def test_crawl_url_escalates_on_crawl4ai_failure(monkeypatch):
    import crawler.registry as reg

    calls: list[str] = []

    async def fake_crawl4ai(url: str, crawler=None):
        calls.append("crawl4ai")
        return empty_page(url, crawler_method="crawl4ai")

    async def fake_cloak(url: str):
        calls.append("cloak")
        return assemble_page(url, markdown="ok from cloak", crawler_method="cloak")

    monkeypatch.setattr(reg.crawl4ai, "fetch_one", fake_crawl4ai)
    monkeypatch.setattr(reg.cloak, "fetch", fake_cloak)
    monkeypatch.setattr(reg, "_resolve_chain", lambda: ["crawl4ai", "cloak"])

    page = await crawl_url("https://example.com")
    assert page["markdown"] == "ok from cloak"
    assert page["crawler_method"] == "cloak"
    assert calls == ["crawl4ai", "cloak"]


@pytest.mark.asyncio
async def test_crawl_pages_batch_escalation(monkeypatch):
    import crawler.registry as reg

    async def fake_crawl4ai(url: str, crawler=None):
        if "fail" in url:
            return empty_page(url, crawler_method="crawl4ai")
        return assemble_page(url, markdown=f"ok {url}", crawler_method="crawl4ai")

    async def fake_cloak(url: str):
        return assemble_page(url, markdown="cloak recovered", crawler_method="cloak")

    async def fake_batch(urls: list[str], indices: list[int]):
        out = []
        for i in indices:
            page = await fake_crawl4ai(urls[i])
            out.append((i, page))
        return out

    monkeypatch.setattr(reg.crawl4ai, "fetch_one", fake_crawl4ai)
    monkeypatch.setattr(reg.cloak, "fetch", fake_cloak)
    monkeypatch.setattr(reg, "_crawl4ai_batch", fake_batch)
    monkeypatch.setattr(reg, "_resolve_chain", lambda: ["crawl4ai", "cloak"])

    urls = ["https://ok.com", "https://fail.com"]
    pages = await crawl_pages(urls)
    assert pages[0]["crawler_method"] == "crawl4ai"
    assert "ok" in pages[0]["markdown"]
    assert pages[1]["crawler_method"] == "cloak"
    assert pages[1]["markdown"] == "cloak recovered"


@pytest.mark.asyncio
async def test_cloak_fetch_parses_subprocess_json(monkeypatch, tmp_path):
    import crawler.cloak as cloak_mod

    script = tmp_path / "fake-cloak.mjs"
    script.write_text("console.log(JSON.stringify({title:'T',content:'<p>hi</p>'}))")

    monkeypatch.setattr(cloak_mod, "resolve_cloak_script", lambda: script)

    async def fake_exec(*args, **kwargs):
        payload = json.dumps({"title": "T", "content": "<p>hi</p>"}).encode()
        proc = type("P", (), {})()
        proc.returncode = 0

        async def communicate():
            return payload, b""

        proc.communicate = communicate
        proc.kill = lambda: None
        proc.wait = lambda: None
        return proc

    monkeypatch.setattr(cloak_mod.asyncio, "create_subprocess_exec", fake_exec)

    page = await cloak_mod.fetch("https://example.com")
    assert page["crawler_method"] == "cloak"
    assert "hi" in page["markdown"]
