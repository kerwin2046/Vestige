from __future__ import annotations

from fastapi.testclient import TestClient

from app import create_app


def _client(tmp_path):
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}"))


def test_ingest_signals_dedupes_by_url(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AGENTS_DIR", str(tmp_path / "agents"))
    with _client(tmp_path) as client:
        created = client.post(
            "/api/companies",
            json={"name": "Acme", "official_domain": "acme.test", "aliases": []},
        )
        assert created.status_code == 201
        company_id = created.json()["data"]["id"]
        assert created.json()["data"]["agent_path"]

        first = client.post(
            f"/api/companies/{company_id}/ingest",
            json={
                "collector": "test",
                "items": [
                    {
                        "url": "https://example.com/a",
                        "title": "A",
                        "source": "rss",
                        "sentiment": "positive",
                    },
                    {
                        "url": "https://example.com/b",
                        "title": "B",
                        "source": "rss",
                    },
                ],
            },
        )
        assert first.status_code == 200
        assert first.json()["data"]["inserted"] == 2
        assert first.json()["data"]["updated"] == 0

        second = client.post(
            f"/api/companies/{company_id}/ingest",
            json={
                "collector": "test",
                "items": [
                    {"url": "https://example.com/a", "title": "A again"},
                    {"url": "https://example.com/c", "title": "C"},
                ],
            },
        )
        assert second.status_code == 200
        assert second.json()["data"]["inserted"] == 1
        assert second.json()["data"]["updated"] == 1

        runs = client.get("/api/runs", params={"company_id": company_id}).json()["data"]
        signal_runs = [r for r in runs if (r.get("settings_snapshot") or {}).get("kind") == "signals"]
        assert len(signal_runs) == 1
        sources = client.get(f"/api/runs/{signal_runs[0]['id']}/sources").json()["data"]
        # Daily audit run only keeps first-seen rows
        assert len(sources) == 3

        ledger = client.get(f"/api/companies/{company_id}/signals").json()["data"]
        assert ledger["total"] == 3
        assert len(ledger["items"]) == 3
        by_url = {item["canonical_url"]: item for item in ledger["items"]}
        assert by_url["https://example.com/a"]["title"] == "A again"


def test_company_signals_span_multiple_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AGENTS_DIR", str(tmp_path / "agents"))
    with _client(tmp_path) as client:
        company_id = client.post(
            "/api/companies",
            json={"name": "Beta", "official_domain": "beta.test", "aliases": []},
        ).json()["data"]["id"]

        client.post(
            f"/api/companies/{company_id}/ingest",
            json={
                "collector": "day1",
                "day": "2026-08-01",
                "items": [{"url": "https://news.test/1", "title": "One"}],
            },
        )
        client.post(
            f"/api/companies/{company_id}/ingest",
            json={
                "collector": "day2",
                "day": "2026-08-02",
                "items": [
                    {"url": "https://news.test/1", "title": "One again"},
                    {"url": "https://news.test/2", "title": "Two"},
                ],
            },
        )

        ledger = client.get(f"/api/companies/{company_id}/signals").json()["data"]
        assert ledger["total"] == 2
        titles = {item["canonical_url"]: item["title"] for item in ledger["items"]}
        assert titles["https://news.test/1"] == "One again"
        assert titles["https://news.test/2"] == "Two"

        # Latest day audit run alone would only show 1 first-seen row
        runs = client.get("/api/runs", params={"company_id": company_id}).json()["data"]
        day2 = next(r for r in runs if (r.get("settings_snapshot") or {}).get("day") == "2026-08-02")
        day2_sources = client.get(f"/api/runs/{day2['id']}/sources").json()["data"]
        assert len(day2_sources) == 1
