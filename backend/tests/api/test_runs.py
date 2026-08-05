from fastapi.testclient import TestClient

from app import create_app
from models import Run, RunSource, RunStatus


def _create_company(client: TestClient) -> str:
    response = client.post(
        "/api/companies",
        json={"name": "Xometry", "official_domain": "xometry.com"},
    )
    return response.json()["data"]["id"]


def test_create_list_get_and_cancel_run(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}")
    with TestClient(app) as client:
        company_id = _create_company(client)
        created = client.post(
            f"/api/companies/{company_id}/runs",
            json={"search_backend": "exa", "max_urls_to_crawl": 12},
        )

        assert created.status_code == 201
        run = created.json()["data"]
        assert run["status"] == "queued"
        assert run["stage"] == "queued"
        assert run["progress"] == 0
        assert run["settings_snapshot"]["search_backend"] == "exa"
        assert run["settings_snapshot"]["lanes"] == [
            "footprint",
            "channels",
            "owned",
        ]
        assert run["settings_snapshot"]["kind"] == "discovery"

        listed = client.get("/api/runs")
        assert [item["id"] for item in listed.json()["data"]] == [run["id"]]

        detail = client.get(f"/api/runs/{run['id']}")
        assert detail.status_code == 200
        assert detail.json()["data"]["company"]["name"] == "Xometry"

        cancelled = client.post(f"/api/runs/{run['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["data"]["status"] == "cancel_requested"


def test_retry_failed_run_creates_new_queued_version(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}")
    with TestClient(app) as client:
        company_id = _create_company(client)
        original = client.post(f"/api/companies/{company_id}/runs", json={}).json()[
            "data"
        ]

        with app.state.database.session_factory() as session:
            failed = session.get(Run, original["id"])
            failed.status = RunStatus.FAILED
            failed.error = "provider unavailable"
            session.commit()

        retried = client.post(f"/api/runs/{original['id']}/retry")

        assert retried.status_code == 201
        new_run = retried.json()["data"]
        assert new_run["id"] != original["id"]
        assert new_run["previous_run_id"] == original["id"]
        assert new_run["status"] == "queued"


def test_list_run_sources(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'vestige.db'}")
    with TestClient(app) as client:
        company_id = _create_company(client)
        run = client.post(f"/api/companies/{company_id}/runs", json={}).json()["data"]

        with app.state.database.session_factory() as session:
            session.add(
                RunSource(
                    run_id=run["id"],
                    url="https://xometry.com/about",
                    canonical_url="https://xometry.com/about",
                    domain="xometry.com",
                    source_type="official_site",
                    ownership="owned",
                    confidence=0.95,
                    title="About Xometry",
                    discovery_path="seed",
                )
            )
            session.commit()

        response = client.get(f"/api/runs/{run['id']}/sources")
        assert response.status_code == 200
        sources = response.json()["data"]
        assert len(sources) == 1
        assert sources[0]["domain"] == "xometry.com"
        assert sources[0]["confidence"] == 0.95

