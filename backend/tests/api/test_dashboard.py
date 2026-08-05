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
    assert data["recent_runs"][0]["id"] == run["id"]

