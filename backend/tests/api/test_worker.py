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

    async def fake_orchestrate(session, *, company, settings, output_dir):
        assert company["name"] == "Xometry"
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        export = out_dir / "sources.xlsx"
        export.write_text("fake")
        return {
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
            ],
            "export_path": str(export),
            "lanes": {"footprint": {"status": "ok", "source_count": 1}},
            "warning": None,
        }

    monkeypatch.setattr("worker.orchestrate_run", fake_orchestrate)

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
        assert detail["settings_snapshot"]["merge"]["total"] == 1

        sources = client.get(f"/api/runs/{run_id}/sources").json()["data"]
        assert len(sources) == 1
        assert sources[0]["domain"] == "xometry.com"
        assert sources[0]["confidence"] == 0.97


def test_worker_merges_previous_footprint_inventory(tmp_path, monkeypatch):
    db_path = tmp_path / "vestige.db"
    app = create_app(database_url=f"sqlite:///{db_path}")

    async def fake_orchestrate(session, *, company, settings, output_dir):
        return {
            "sources": [
                {
                    "url": "https://xometry.com/new",
                    "canonical_url": "https://xometry.com/new",
                    "domain": "xometry.com",
                    "source_type": "news_media",
                    "ownership": "third_party",
                    "confidence": 0.8,
                    "title": "New",
                    "snippet": "fresh",
                    "discovery_path": "search",
                    "bfs_round": 0,
                    "detail": None,
                }
            ],
            "export_path": None,
            "lanes": {"footprint": {"status": "ok", "source_count": 1}},
            "warning": None,
        }

    monkeypatch.setattr("worker.orchestrate_run", fake_orchestrate)

    with TestClient(app) as client:
        company_id = client.post(
            "/api/companies",
            json={"name": "Xometry", "official_domain": "xometry.com"},
        ).json()["data"]["id"]

        # Seed a prior successful footprint run with one source
        first = client.post(f"/api/companies/{company_id}/runs", json={}).json()["data"]
        with app.state.database.session_factory() as session:
            from repositories import runs as runs_repo

            runs_repo.replace_run_sources(
                session,
                first["id"],
                [
                    {
                        "url": "https://xometry.com/about",
                        "canonical_url": "https://xometry.com/about",
                        "domain": "xometry.com",
                        "source_type": "owned",
                        "ownership": "first_party",
                        "confidence": 0.9,
                        "title": "About",
                        "snippet": "old",
                        "discovery_path": "owned",
                        "bfs_round": 0,
                    }
                ],
            )
            run = session.get(Run, first["id"])
            run.status = RunStatus.SUCCEEDED
            run.stage = "succeeded"
            run.progress = 100
            session.commit()

        second = client.post(f"/api/companies/{company_id}/runs", json={}).json()["data"]
        with app.state.database.session_factory() as session:
            run = session.get(Run, second["id"])
            run.status = RunStatus.RUNNING
            session.commit()

        asyncio.run(process_run(app.state.database, second["id"]))

        detail = client.get(f"/api/runs/{second['id']}").json()["data"]
        assert detail["status"] == "succeeded"
        merge = detail["settings_snapshot"]["merge"]
        assert merge["added"] == 1
        assert merge["kept"] == 1
        assert merge["total"] == 2

        sources = client.get(f"/api/runs/{second['id']}/sources").json()["data"]
        urls = {s["canonical_url"] for s in sources}
        assert urls == {
            "https://xometry.com/about",
            "https://xometry.com/new",
        }


def test_worker_marks_failed_on_exception(tmp_path, monkeypatch):
    db_path = tmp_path / "vestige.db"
    app = create_app(database_url=f"sqlite:///{db_path}")

    async def boom(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("worker.orchestrate_run", boom)

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
