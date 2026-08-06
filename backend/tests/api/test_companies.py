from fastapi.testclient import TestClient

from app import create_app


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}"))


def test_company_crud_round_trip(tmp_path):
    with _client(tmp_path) as client:
        created = client.post(
            "/api/companies",
            json={
                "name": "Xometry",
                "official_domain": "https://www.xometry.com/",
                "industry": "Manufacturing",
                "location": "US",
                "aliases": ["Xometry Inc.", " Xometry Inc. "],
            },
        )

        assert created.status_code == 201
        company = created.json()["data"]
        assert company["official_domain"] == "xometry.com"
        assert company["aliases"] == ["Xometry Inc."]

        listed = client.get("/api/companies")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["data"]] == [company["id"]]

        updated = client.put(
            f"/api/companies/{company['id']}",
            json={
                "name": "Xometry",
                "official_domain": "xometry.com",
                "industry": "On-demand manufacturing",
                "location": "US",
                "aliases": ["Xometry Inc."],
            },
        )
        assert updated.status_code == 200
        assert updated.json()["data"]["industry"] == "On-demand manufacturing"

        deleted = client.delete(f"/api/companies/{company['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["data"] == {"deleted": True}
        assert client.get("/api/companies").json()["data"] == []


def test_company_list_includes_activity(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AGENTS_DIR", str(tmp_path / "agents"))
    with _client(tmp_path) as client:
        company = client.post(
            "/api/companies",
            json={"name": "Acme", "official_domain": "acme.test", "aliases": []},
        ).json()["data"]
        ingest = client.post(
            f"/api/companies/{company['id']}/ingest",
            json={
                "collector": "test",
                "items": [
                    {"url": "https://news.test/a", "title": "A", "confidence": 0.9},
                ],
            },
        )
        assert ingest.status_code == 200

        listed = client.get("/api/companies")
        assert listed.status_code == 200
        row = listed.json()["data"][0]
        assert row["activity"]["signal_count"] == 1
        assert row["activity"]["signals_today"] == 1
        assert row["activity"]["active_24h"] is True
        assert row["activity"]["last_signal_at"]

        rev = client.get("/api/companies/activity-revision")
        assert rev.status_code == 200
        assert rev.json()["data"]["revision"]
        assert rev.json()["data"]["signal_count"] >= 1

        bare = client.get("/api/companies", params={"include_activity": False})
        assert "activity" not in bare.json()["data"][0]


def test_company_name_is_required(tmp_path):
    with _client(tmp_path) as client:
        response = client.post("/api/companies", json={"name": "   "})

    assert response.status_code == 422

