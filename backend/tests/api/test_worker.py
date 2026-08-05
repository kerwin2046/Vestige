from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from models import Run, RunStatus
from worker import process_run


def test_worker_persists_sources_and_marks_succeeded(tmp_path, monkeypatch):
    db_path = tmp_path / "vestige.db"
    app = create_app(database_url=f"sqlite:///{db_path}")

    async def fake_run_company(**kwargs):
        assert kwargs["name"] == "Xometry"
        assert kwargs["official_domain"] == "xometry.com"
        out_dir = Path(kwargs["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        export = out_dir / "sources.xlsx"
        export.write_text("fake")
        return {
            "result": {
                "sources": [
                    {
                        "url": "https://xometry.com/about",
                        "canonical_url": "https://xometry.com/about",
                        "domain": "xometry.com",
                        "source_type": "official_site",
                        "ownership": "first_party",
                        "confidence": 0.97,
                        "title": "About",
                        "snippet": "Xometry",
                        "discovery_path": "seed",
                        "bfs_round": 0,
                        "detail": None,
                    }
                ]
            },
            "report": "ok",
            "export_path": str(export),
        }

    monkeypatch.setattr("worker.run_company", fake_run_company)

    with TestClient(app) as client:
        company_id = client.post(
            "/api/companies",
            json={"name": "Xometry", "official_domain": "xometry.com"},
        ).json()["data"]["id"]
        run_id = client.post(f"/api/companies/{company_id}/runs", json={}).json()[
            "data"
        ]["id"]

        with app.state.database.session_factory() as session:
            run = session.get(Run, run_id)
            run.status = RunStatus.RUNNING
            run.stage = "starting"
            session.commit()

        asyncio.run(process_run(app.state.database, run_id))

        detail = client.get(f"/api/runs/{run_id}").json()["data"]
        assert detail["status"] == "succeeded"
        assert detail["progress"] == 100
        assert detail["export_path"]

        sources = client.get(f"/api/runs/{run_id}/sources").json()["data"]
        assert len(sources) == 1
        assert sources[0]["domain"] == "xometry.com"
        assert sources[0]["confidence"] == 0.97


def test_worker_marks_failed_on_exception(tmp_path, monkeypatch):
    db_path = tmp_path / "vestige.db"
    app = create_app(database_url=f"sqlite:///{db_path}")

    async def boom(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("worker.run_company", boom)

    with TestClient(app) as client:
        company_id = client.post(
            "/api/companies",
            json={"name": "Acme", "official_domain": "acme.com"},
        ).json()["data"]["id"]
        run_id = client.post(f"/api/companies/{company_id}/runs", json={}).json()[
            "data"
        ]["id"]

        with app.state.database.session_factory() as session:
            run = session.get(Run, run_id)
            run.status = RunStatus.RUNNING
            session.commit()

        try:
            asyncio.run(process_run(app.state.database, run_id))
        except RuntimeError:
            pass

        detail = client.get(f"/api/runs/{run_id}").json()["data"]
        assert detail["status"] == "failed"
        assert "provider unavailable" in detail["error"]
