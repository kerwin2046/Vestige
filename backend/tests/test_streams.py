"""Tests for Intel Streams (models, ingest, pulse origin)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import create_app
from application.pulse_feed import build_pulse_feed
from application.stream_ingest import ingest_stream_signals
from database import Database
from models import Company, CompanySignal
from repositories import stream_signals as streams_repo
from sqlalchemy import select


def _db(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    database.create_all()
    return database


def test_upsert_stream_signal_unique(tmp_path):
    db = _db(tmp_path)
    with db.session_factory() as session:
        stream = streams_repo.ensure_mfg_social_stream(session)
        row, created = streams_repo.upsert_stream_signal(
            session,
            stream_id=stream.id,
            url="https://www.practicalmachinist.com/threads/a.1/",
            canonical_url="https://www.practicalmachinist.com/threads/a.1/",
            title="First",
            confidence=0.6,
            source_type="community_ugc",
        )
        session.commit()
        assert created is True
        row2, created2 = streams_repo.upsert_stream_signal(
            session,
            stream_id=stream.id,
            url="https://www.practicalmachinist.com/threads/a.1/",
            canonical_url="https://www.practicalmachinist.com/threads/a.1/",
            title="Updated",
            confidence=0.8,
            source_type="community_ugc",
        )
        session.commit()
        assert created2 is False
        assert row2.id == row.id
        assert row2.title == "Updated"
        assert row2.confidence == 0.8
        assert streams_repo.count_stream_signals(session, stream.id) == 1


def test_stream_ingest_and_api(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'api.db'}"
    db = Database(db_url)
    db.create_all()
    with db.session_factory() as session:
        streams_repo.ensure_mfg_social_stream(session)

    client = TestClient(create_app(db_url))
    resp = client.post(
        "/api/streams/mfg-social/ingest",
        json={
            "collector": "test",
            "items": [
                {
                    "url": "https://reddit.com/r/CNC/comments/abc",
                    "title": "Lead times insane",
                    "snippet": "shops quoting 12 weeks",
                    "source_type": "community_ugc",
                    "confidence": 0.75,
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["inserted"] == 1

    listed = client.get("/api/streams")
    assert listed.status_code == 200
    streams = listed.json()["data"]
    assert any(s["slug"] == "mfg-social" for s in streams)

    signals = client.get("/api/streams/mfg-social/signals")
    assert signals.status_code == 200
    page = signals.json()["data"]
    assert page["total"] >= 1


def test_pulse_includes_stream_origin(tmp_path):
    db = _db(tmp_path)
    with db.session_factory() as session:
        stream = streams_repo.ensure_mfg_social_stream(session)
        ingest_stream_signals(
            session,
            stream_id=stream.id,
            items=[
                {
                    "url": "https://www.practicalmachinist.com/threads/hot.99/",
                    "title": "Hot thread",
                    "confidence": 0.9,
                    "source_type": "community_ugc",
                }
            ],
            collector="test",
        )
        company = Company(name="Acme", official_domain="acme.test", tier="monitoring")
        session.add(company)
        session.commit()
        session.refresh(company)
        session.add(
            CompanySignal(
                company_id=company.id,
                url="https://news.example/acme",
                canonical_url="https://news.example/acme",
                domain="news.example",
                source_type="news_media",
                confidence=0.85,
                title="Acme news",
                last_seen_at=datetime.now(timezone.utc),
                first_seen_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        pulse = build_pulse_feed(session, limit=20, min_fill=1)
        origins = {item["row"].origin for item in pulse["must_see"] + pulse["feed"]}
        assert "stream" in origins
        assert "company" in origins
        assert any(item["row"].origin == "stream" for item in pulse["industry_pulse"])


def test_migrate_generic_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "mig.db"
    monkeypatch.setenv("VESTIGE_DATABASE_URL", f"sqlite:///{db_path}")
    db = Database(f"sqlite:///{db_path}")
    db.create_all()
    with db.session_factory() as session:
        company = Company(name="通用", official_domain="", tier="target")
        session.add(company)
        session.commit()
        session.refresh(company)
        session.add(
            CompanySignal(
                company_id=company.id,
                url="https://www.bilibili.com/video/BV1",
                canonical_url="https://www.bilibili.com/video/BV1",
                domain="bilibili.com",
                source_type="social",
                confidence=0.5,
                title="old dump",
            )
        )
        session.commit()

    from scripts.migrate_generic_to_stream import migrate

    first = migrate(dry_run=False)
    assert first["copied"] == 1
    second = migrate(dry_run=False)
    assert second["copied"] == 0
    assert second["skipped_existing"] == 1

    with db.session_factory() as session:
        stream = streams_repo.get_stream_by_slug(session, "mfg-social")
        assert stream is not None
        assert streams_repo.count_stream_signals(session, stream.id) == 1
        dump = session.scalar(select(Company).where(Company.name == "通用"))
        assert dump is not None
        assert dump.directory_hidden == 1
        from repositories import companies as companies_repo

        listed = companies_repo.list_companies(session)
        assert all(c.name != "通用" for c in listed)
