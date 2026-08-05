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

        runs = client.get("/api/runs", params={"company_id": company_id}).json()["data"]
        signal_runs = [r for r in runs if (r.get("settings_snapshot") or {}).get("kind") == "signals"]
        assert len(signal_runs) == 1
        sources = client.get(f"/api/runs/{signal_runs[0]['id']}/sources").json()["data"]
        assert len(sources) == 3
