import sqlite3

from fastapi.testclient import TestClient

from app import create_app


def test_health_returns_success_envelope(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'vestige.db'}"
    app = create_app(database_url=database_url)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {"status": "ok"},
    }

    with sqlite3.connect(tmp_path / "vestige.db") as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"companies", "runs", "run_sources", "run_events"} <= tables

