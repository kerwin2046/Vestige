"""Tests for OpenClaw agent command builder (no live gateway)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from application.openclaw_agent import build_openclaw_command, build_task_message, write_task_file


def test_build_task_message_includes_ingest_url(tmp_path, monkeypatch):
    monkeypatch.setenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")
    company = SimpleNamespace(
        id="abc-123",
        name="Xometry",
        official_domain="xometry.com",
        industry="manufacturing",
        location="US",
        tier="target",
        roles=["competitor"],
    )
    agent_dir = tmp_path / "xometry"
    agent_dir.mkdir()
    text = build_task_message(company, agent_dir)
    assert "abc-123" in text
    assert "/api/companies/abc-123/ingest" in text
    assert "AGENT.md" in text


def test_build_openclaw_command_session_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_BIN", "/usr/bin/openclaw")
    agent_dir = tmp_path / "xometry"
    agent_dir.mkdir()
    task = agent_dir / "TASK.md"
    task.write_text("hi", encoding="utf-8")
    cmd = build_openclaw_command(
        agent_dir=agent_dir,
        task_path=task,
        openclaw_agent="main",
        local=True,
        timeout_seconds=120,
    )
    assert cmd[0] == "/usr/bin/openclaw"
    assert "--agent" in cmd and "main" in cmd
    assert "--session-key" in cmd
    assert "agent:main:vestige:xometry" in cmd
    assert "--local" in cmd
    assert "--message-file" in cmd
    assert str(task) in cmd


def test_write_task_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")
    company = SimpleNamespace(
        id="c1",
        name="Fictiv",
        official_domain="fictiv.com",
        industry="",
        location="",
        tier="target",
        roles=["competitor"],
    )
    agent_dir = tmp_path / "fictiv"
    agent_dir.mkdir()
    path = write_task_file(company, agent_dir)
    assert path == agent_dir / "TASK.md"
    assert path.is_file()
    assert "Fictiv" in path.read_text(encoding="utf-8")
