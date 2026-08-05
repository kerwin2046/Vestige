"""Invoke OpenClaw to run a Vestige per-company agent workspace.

Scaffold lays down ~/.openclaw/workspace/agents/<slug>/AGENT.md.
This module turns that into a live OpenClaw agent turn:

  openclaw agent --agent main \\
    --session-key agent:main:vestige:<slug> \\
    --message-file <agent>/TASK.md

Gateway must be running (`openclaw gateway` / daemon). Use --local to bypass.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from application.scaffold_agent import company_slug, scaffold_company_agent
from models import Company

DEFAULT_OPENCLAW_AGENT = "main"


def resolve_openclaw_bin() -> str:
    explicit = (os.getenv("OPENCLAW_BIN") or "").strip()
    if explicit:
        return explicit
    found = shutil.which("openclaw")
    if found:
        return found
    # Common npm-global install when PATH is thin (API / make without nvm).
    home = Path.home()
    candidates = [
        home / ".npm-global" / "bin" / "openclaw",
        home / ".local" / "bin" / "openclaw",
        Path("/usr/local/bin/openclaw"),
    ]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise FileNotFoundError(
        "openclaw CLI not found. Install OpenClaw or set OPENCLAW_BIN."
    )


def ensure_node_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Prefer Node ≥22 on PATH (nvm) so openclaw CLI can start."""
    out = dict(os.environ if env is None else env)
    if out.get("OPENCLAW_NODE_BIN"):
        node_bin = Path(out["OPENCLAW_NODE_BIN"])
        if node_bin.is_dir():
            out["PATH"] = f"{node_bin}:{out.get('PATH', '')}"
        return out

    nvm_versions = Path.home() / ".nvm" / "versions" / "node"
    if nvm_versions.is_dir():
        # Prefer newest v22+/v24+ directory name
        versions = sorted(
            [p for p in nvm_versions.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for ver in versions:
            major = ver.name.lstrip("v").split(".")[0]
            try:
                if int(major) >= 22:
                    out["PATH"] = f"{ver / 'bin'}:{out.get('PATH', '')}"
                    break
            except ValueError:
                continue
    return out


def build_task_message(company: Company, agent_dir: Path) -> str:
    api = os.getenv("VESTIGE_API_BASE", "http://127.0.0.1:8001").rstrip("/")
    return f"""# Vestige OpenClaw task — {company.name}

You are the competitive-intel agent for this company. Execute the daily routine now.

## Context files (read these first)
- Agent brief: `{agent_dir / "AGENT.md"}`
- Sources: `{agent_dir / "sources.yaml"}`
- Company meta: `{agent_dir / "company.json"}`

## Company
- Vestige id: `{company.id}`
- Name: {company.name}
- Domain: {company.official_domain or "(none)"}
- Industry: {company.industry or "(none)"}
- Location: {company.location or "(none)"}
- Tier / roles: {company.tier} / {", ".join(company.roles or []) or "(none)"}

## Required actions
1. Follow AGENT.md mission for **today only** (incremental signals).
2. Collect real URLs / titles / snippets (do not invent).
3. POST results to Vestige ingest:
   `POST {api}/api/companies/{company.id}/ingest`
   Body shape:
   ```json
   {{
     "collector": "openclaw:{agent_dir.name}",
     "items": [
       {{
         "url": "https://...",
         "title": "...",
         "snippet": "...",
         "source": "web",
         "confidence": 0.7
       }}
     ]
   }}
   ```
4. If nothing new is found, POST an empty `items` list and say so.
5. Reply with a short summary: searches tried, items posted, errors.

Work only on this company. Prefer official / reviews / news / filings over random directories.
"""


def write_task_file(company: Company, agent_dir: Path) -> Path:
    task_path = agent_dir / "TASK.md"
    task_path.write_text(build_task_message(company, agent_dir), encoding="utf-8")
    return task_path


def build_openclaw_command(
    *,
    agent_dir: Path,
    task_path: Path,
    openclaw_agent: str = DEFAULT_OPENCLAW_AGENT,
    local: bool = False,
    timeout_seconds: int = 600,
    thinking: str | None = None,
) -> list[str]:
    slug = agent_dir.name
    cmd = [
        resolve_openclaw_bin(),
        "agent",
        "--agent",
        openclaw_agent,
        "--session-key",
        f"agent:{openclaw_agent}:vestige:{slug}",
        "--message-file",
        str(task_path),
        "--json",
        "--timeout",
        str(timeout_seconds),
    ]
    if local:
        cmd.append("--local")
    if thinking:
        cmd.extend(["--thinking", thinking])
    return cmd


def run_company_openclaw_agent(
    company: Company,
    *,
    wait: bool = True,
    local: bool = False,
    timeout_seconds: int = 600,
    thinking: str | None = None,
    openclaw_agent: str | None = None,
    scaffold: bool = True,
) -> dict[str, Any]:
    """Scaffold (optional) + invoke OpenClaw for this company agent."""
    if scaffold:
        agent_dir = scaffold_company_agent(company)
    else:
        from application.scaffold_agent import agents_root

        agent_dir = agents_root() / company_slug(company)
        if not agent_dir.exists():
            agent_dir = scaffold_company_agent(company)

    task_path = write_task_file(company, agent_dir)
    agent_id = openclaw_agent or os.getenv("OPENCLAW_AGENT_ID", DEFAULT_OPENCLAW_AGENT)
    cmd = build_openclaw_command(
        agent_dir=agent_dir,
        task_path=task_path,
        openclaw_agent=agent_id,
        local=local or os.getenv("OPENCLAW_LOCAL", "").lower() in {"1", "true", "yes"},
        timeout_seconds=timeout_seconds,
        thinking=thinking,
    )

    log_path = agent_dir / "last_run.log"
    env = ensure_node_env()
    started = time.time()
    meta: dict[str, Any] = {
        "company_id": company.id,
        "company_name": company.name,
        "slug": agent_dir.name,
        "agent_path": str(agent_dir),
        "task_path": str(task_path),
        "log_path": str(log_path),
        "command": cmd,
        "openclaw_agent": agent_id,
        "wait": wait,
        "local": "--local" in cmd,
    }

    if wait:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"$ {' '.join(cmd)}\n\n")
            log.flush()
            proc = subprocess.run(
                cmd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds + 30,
            )
        meta["pid"] = None
        meta["returncode"] = proc.returncode
        meta["elapsed_seconds"] = round(time.time() - started, 2)
        meta["status"] = "succeeded" if proc.returncode == 0 else "failed"
        meta["log_tail"] = _tail(log_path, 40)
        if proc.returncode != 0:
            raise RuntimeError(
                f"openclaw agent failed (exit {proc.returncode}). "
                f"See {log_path}"
            )
        return meta

    # Detached: leave process running; caller inspects last_run.log
    log_fh = log_path.open("w", encoding="utf-8")
    log_fh.write(f"$ {' '.join(cmd)}\n\n")
    log_fh.flush()
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    meta["pid"] = proc.pid
    meta["returncode"] = None
    meta["status"] = "started"
    meta["elapsed_seconds"] = round(time.time() - started, 2)
    # Keep log_fh open for the child; drop our reference.
    return meta


def _tail(path: Path, lines: int = 40) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(content[-lines:])
