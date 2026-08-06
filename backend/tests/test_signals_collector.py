"""Tests for shared signals collector (no live OpenClaw)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from application.signals_collector import (
    COLLECTOR_SLUG,
    build_shared_task_message,
    scaffold_signals_collector,
    select_dispatch_queue,
    use_shared_collector_by_default,
    write_shared_task,
)


def test_scaffold_signals_collector(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AGENTS_DIR", str(tmp_path))
    monkeypatch.setenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")
    path = scaffold_signals_collector()
    assert path == tmp_path / COLLECTOR_SLUG
    assert (path / "AGENT.md").is_file()
    assert (path / "sources.yaml").is_file()
    assert (path / "collector.json").is_file()
    assert "signals-collector" in (path / "AGENT.md").read_text(encoding="utf-8")


def test_write_shared_task(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AGENTS_DIR", str(tmp_path))
    monkeypatch.setenv("VESTIGE_API_BASE", "http://example.test")
    collector = scaffold_signals_collector()
    company = SimpleNamespace(
        id="c-1",
        name="Xometry",
        official_domain="xometry.com",
        industry="mfg",
        location="US",
        tier="monitoring",
        roles=["competitor"],
        priority="high",
        aliases=["Xometry Inc"],
    )
    task = write_shared_task(company, collector)
    assert task.name.endswith(".md")
    text = task.read_text(encoding="utf-8")
    assert "c-1" in text
    assert "/api/companies/c-1/ingest" in text
    assert "openclaw:signals-collector" in text
    assert (collector / "TASK.md").read_text(encoding="utf-8") == text


def test_build_shared_task_message_company_only(tmp_path, monkeypatch):
    monkeypatch.setenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")
    company = SimpleNamespace(
        id="id-9",
        name="Fictiv",
        official_domain="fictiv.com",
        industry="",
        location="",
        tier="target",
        roles=[],
        priority=None,
        aliases=[],
    )
    msg = build_shared_task_message(company, tmp_path)
    assert "this company only" in msg.lower() or "Do not work on any other company" in msg
    assert "Fictiv" in msg


def test_select_dispatch_queue_prefers_never_seen():
    now = datetime.now(timezone.utc)
    never = SimpleNamespace(
        id="1",
        name="A",
        tier="monitoring",
        roles=[],
        priority="high",
        last_signal_at=None,
    )
    fresh = SimpleNamespace(
        id="2",
        name="B",
        tier="monitoring",
        roles=[],
        priority="high",
        last_signal_at=now - timedelta(hours=1),
    )
    stale = SimpleNamespace(
        id="3",
        name="C",
        tier="monitoring",
        roles=[],
        priority="low",
        last_signal_at=now - timedelta(hours=48),
    )

    class FakeSession:
        def scalars(self, _stmt):
            return [never, fresh, stale]

    queue = select_dispatch_queue(FakeSession(), limit=10, tier="monitoring", stale_only=True)
    ids = [c.id for c in queue]
    assert "2" not in ids  # fresh filtered
    assert ids[0] == "1"  # never-seen first


def test_use_shared_collector_by_default(monkeypatch):
    monkeypatch.delenv("VESTIGE_SHARED_COLLECTOR", raising=False)
    assert use_shared_collector_by_default() is True
    monkeypatch.setenv("VESTIGE_SHARED_COLLECTOR", "0")
    assert use_shared_collector_by_default() is False
    monkeypatch.setenv("VESTIGE_SHARED_COLLECTOR", "per-company")
    assert use_shared_collector_by_default() is False
