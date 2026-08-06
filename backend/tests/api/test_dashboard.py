from fastapi.testclient import TestClient

from app import create_app


def test_dashboard_summarizes_companies_and_runs(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}")
    with TestClient(app) as client:
        company = client.post(
            "/api/companies",
            json={"name": "Xometry", "official_domain": "xometry.com"},
        ).json()["data"]
        run = client.post(f"/api/companies/{company['id']}/runs", json={}).json()[
            "data"
        ]

        response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["company_count"] == 1
    assert data["run_count"] == 1
    assert data["queued_count"] == 1
    assert data["source_count"] == 0
    assert data["signal_count"] == 0
    assert data["signals_today"] == 0
    assert data["pulse"]["must_see"] == []
    assert data["pulse"]["feed"] == []
    assert data["pulse"]["limit"] == 25
    assert data["recent_signals"] == []
    assert data["recent_insights"] == []
    assert len(data["signal_series"]) == 7
    assert data["top_signal_types"] == []
    assert data["recent_runs"][0]["id"] == run["id"]


def test_dashboard_signal_feed_includes_company(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AGENTS_DIR", str(tmp_path / "agents"))
    app = create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}")
    with TestClient(app) as client:
        company = client.post(
            "/api/companies",
            json={"name": "Acme", "official_domain": "acme.test", "aliases": []},
        ).json()["data"]
        ingest = client.post(
            f"/api/companies/{company['id']}/ingest",
            json={
                "collector": "test",
                "items": [
                    {
                        "url": "https://news.test/acme-raises",
                        "title": "Acme raises Series B",
                        "snippet": "Funding news",
                        "source_type": "news_media",
                        "confidence": 0.9,
                    }
                ],
            },
        )
        assert ingest.status_code == 200

        response = client.get("/api/dashboard")

    data = response.json()["data"]
    assert data["signal_count"] == 1
    assert data["signals_today"] == 1
    assert len(data["pulse"]["must_see"]) + len(data["pulse"]["feed"]) == 1
    item = (data["pulse"]["must_see"] or data["pulse"]["feed"])[0]
    assert item["title"] == "Acme raises Series B"
    assert item["company"]["name"] == "Acme"
    assert item["company_id"] == company["id"]
    assert "score" in item
    assert data["recent_insights"][0]["title"] == "Acme raises Series B"
    assert any(row["key"] == "news_media" for row in data["top_signal_types"])
    assert sum(point["total"] for point in data["signal_series"]) >= 1

    feed = client.get("/api/dashboard/feed", params={"limit": 10, "offset": 0})
    assert feed.status_code == 200
    assert "has_more" in feed.json()["data"]
