from application.run_company import run_company


def test_run_company_uses_request_scoped_anchor(monkeypatch):
    captured = {}

    async def fake_discovery(*, anchor, settings=None, output_dir=None, write_excel=True):
        captured["anchor"] = anchor
        captured["settings"] = settings
        captured["output_dir"] = output_dir
        captured["write_excel"] = write_excel
        return {
            "result": {"sources": []},
            "report": "empty",
            "export_path": None,
        }

    monkeypatch.setattr(
        "application.run_company.run_company_discovery", fake_discovery
    )

    import asyncio

    outcome = asyncio.run(
        run_company(
            name="Xometry",
            official_domain="xometry.com",
            industry="Manufacturing",
            location="US",
            aliases=["Xometry Inc"],
            settings={"max_urls_to_crawl": 3},
            output_dir="output/runs/test",
            write_excel=False,
        )
    )

    assert outcome["report"] == "empty"
    assert captured["anchor"] == {
        "name": "Xometry",
        "official_domain": "xometry.com",
        "industry": "Manufacturing",
        "location": "US",
        "aliases": ["Xometry Inc"],
    }
    assert captured["settings"] == {"max_urls_to_crawl": 3}
    assert captured["write_excel"] is False
