"""Unit tests for multi-lane discovery orchestration."""

from __future__ import annotations

import pytest

from application.orchestrate import DiscoveryEmptyError, orchestrate_run
from database import Database
from models import Channel


@pytest.mark.asyncio
async def test_orchestrate_fails_when_all_lanes_empty(tmp_path, monkeypatch):
    db = Database(f"sqlite:///{tmp_path / 'vestige.db'}")
    db.create_all()

    async def fake_footprint(*, company, settings, output_dir):
        return {
            "lane": "footprint",
            "status": "empty",
            "sources": [],
            "export_path": None,
            "error": "no inventory",
        }

    monkeypatch.setattr(
        "application.orchestrate._lane_footprint",
        fake_footprint,
    )

    with db.session_factory() as session:
        company = {
            "name": "Ghost Co",
            "official_domain": "",
            "industry": "",
            "location": "",
            "aliases": [],
        }
        with pytest.raises(DiscoveryEmptyError, match="no usable hits"):
            await orchestrate_run(
                session,
                company=company,
                settings={"lanes": ["footprint", "channels", "owned"]},
                output_dir=str(tmp_path / "out"),
            )


@pytest.mark.asyncio
async def test_orchestrate_merges_channel_hits(tmp_path, monkeypatch):
    db = Database(f"sqlite:///{tmp_path / 'vestige.db'}")
    db.create_all()
    with db.session_factory() as session:
        session.add(
            Channel(
                kind="platform",
                name="Test B2B",
                url="https://example-b2b.com",
                domain="example-b2b.com",
                industry="manufacturing",
                score=0.9,
                has_member_directory=1,
            )
        )
        session.commit()

    async def fake_footprint(*, company, settings, output_dir):
        return {
            "lane": "footprint",
            "status": "empty",
            "sources": [],
            "export_path": None,
            "error": "CAPTCHA",
        }

    async def fake_channels(session, *, company, settings):
        return {
            "lane": "channels",
            "status": "ok",
            "sources": [
                {
                    "url": "https://example-b2b.com/co/acme",
                    "canonical_url": "https://example-b2b.com/co/acme",
                    "domain": "example-b2b.com",
                    "source_type": "marketplace_directory",
                    "ownership": "third_party",
                    "confidence": 0.55,
                    "title": "Acme",
                    "snippet": "hit",
                    "discovery_path": "channel:site",
                    "bfs_round": 0,
                    "detail": {"lane": "channels"},
                }
            ],
            "error": None,
            "meta": {"hit_count": 1},
        }

    monkeypatch.setattr("application.orchestrate._lane_footprint", fake_footprint)
    monkeypatch.setattr("application.orchestrate._lane_channels", fake_channels)

    with db.session_factory() as session:
        outcome = await orchestrate_run(
            session,
            company={
                "name": "Acme",
                "official_domain": "acme.com",
                "industry": "manufacturing",
                "location": "",
                "aliases": [],
            },
            settings={"lanes": ["footprint", "channels", "owned"]},
            output_dir=str(tmp_path / "out"),
        )

    assert len(outcome["sources"]) >= 2  # channel hit + owned
    assert outcome["lanes"]["footprint"]["status"] == "empty"
    assert outcome["lanes"]["channels"]["status"] == "ok"
    assert outcome["lanes"]["owned"]["status"] == "ok"
    assert outcome["warning"]
    assert any(s["domain"] == "example-b2b.com" for s in outcome["sources"])
    assert any(s["domain"] == "acme.com" for s in outcome["sources"])
