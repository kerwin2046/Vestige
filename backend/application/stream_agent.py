"""Dedicated OpenClaw agent for Manufacturing Social Pulse (Intel Stream)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from application.openclaw_agent import DEFAULT_OPENCLAW_AGENT, ensure_node_env, resolve_openclaw_bin
from application.scaffold_agent import agents_root
from models import IntelStream
from repositories import stream_signals as streams_repo

AGENT_SLUG = "mfg-social-pulse"


def agent_dir() -> Path:
    return agents_root() / AGENT_SLUG


def scaffold_mfg_social_agent(*, vestige_api: str | None = None) -> Path:
    path = agent_dir()
    path.mkdir(parents=True, exist_ok=True)
    (path / "logs").mkdir(exist_ok=True)

    api = (vestige_api or os.getenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")).rstrip(
        "/"
    )

    agent_md = f"""# Agent: Manufacturing Social Pulse

## Mission
You collect **industry community heat** for manufacturing — not one company.
Post findings to Vestige Intel Stream `mfg-social`.

## Focus platforms
- Practical Machinist — https://www.practicalmachinist.com/
- Reddit: r/Machinists, r/CNC, r/manufacturing, r/AdditiveManufacturing
- LinkedIn manufacturing discussions (public posts you can reach)
- Related machining / job-shop / additive forums

## Topics
CNC capacity, quoting/lead times, metal AM, tooling, shop-floor pain, hiring.

## Rules
- Prefer **today / last 48h** threads with real engagement.
- Do not invent URLs. Prefer `community_ugc` or `social` source_type.
- Optional `detail.themes` / `detail.mentioned_domains` when a competitor is named.
- If nothing new: POST empty `items`.

## Ingest
`POST {api}/api/streams/mfg-social/ingest`

```json
{{
  "collector": "openclaw:mfg-social-pulse",
  "items": [
    {{
      "url": "https://...",
      "title": "...",
      "snippet": "...",
      "source_type": "community_ugc",
      "confidence": 0.7,
      "source": "practicalmachinist"
    }}
  ]
}}
```
"""

    sources = """# Manufacturing Social Pulse sources
platforms:
  - id: practicalmachinist
    url: https://www.practicalmachinist.com/
  - id: reddit
    subs: [Machinists, CNC, manufacturing, AdditiveManufacturing]
  - id: linkedin
    queries:
      - CNC machining
      - contract manufacturing
      - metal 3D printing
"""

    (path / "AGENT.md").write_text(agent_md, encoding="utf-8")
    (path / "sources.yaml").write_text(sources, encoding="utf-8")
    (path / "collector.json").write_text(
        json.dumps(
            {
                "slug": AGENT_SLUG,
                "stream_slug": "mfg-social",
                "vestige_api": api,
                "mode": "stream",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def build_stream_task(stream: IntelStream, path: Path) -> str:
    api = os.getenv("VESTIGE_API_BASE", "http://127.0.0.1:8001").rstrip("/")
    sources_preview = json.dumps(stream.sources or {}, ensure_ascii=False, indent=2)[:2000]
    return f"""# Vestige stream task — {stream.name}

You are the **mfg-social-pulse** agent. Collect today's manufacturing community heat.

## Stream
- id: `{stream.id}`
- slug: `{stream.slug}`
- kind: {stream.kind}

## Brief
- `{path / "AGENT.md"}`
- `{path / "sources.yaml"}`

## Configured sources
```json
{sources_preview}
```

## Actions
1. Scan Practical Machinist / Reddit manufacturing subs / LinkedIn public posts for hot threads (last 48h).
2. Filter noise; keep machining / CNC / AM / job-shop relevant items.
3. POST to `{api}/api/streams/{stream.slug}/ingest` with collector `openclaw:mfg-social-pulse`.
4. Reply with counts: searched, posted, skipped.

Do not run company-specific footprint discovery.
"""


def write_stream_task(stream: IntelStream, path: Path) -> Path:
    task = path / "TASK.md"
    task.write_text(build_stream_task(stream, path), encoding="utf-8")
    return task


def run_mfg_social_pulse(
    session: Session,
    *,
    stream: IntelStream | None = None,
    wait: bool = False,
    local: bool = False,
    timeout_seconds: int = 600,
    thinking: str | None = None,
    openclaw_agent: str | None = None,
) -> dict[str, Any]:
    target = stream or streams_repo.ensure_mfg_social_stream(session)
    path = scaffold_mfg_social_agent()
    task_path = write_stream_task(target, path)
    agent_id = openclaw_agent or os.getenv("OPENCLAW_AGENT_ID", DEFAULT_OPENCLAW_AGENT)

    cmd = [
        resolve_openclaw_bin(),
        "agent",
        "--agent",
        agent_id,
        "--session-key",
        f"agent:{agent_id}:vestige:stream:{target.slug}",
        "--message-file",
        str(task_path),
        "--json",
        "--timeout",
        str(timeout_seconds),
    ]
    if local or os.getenv("OPENCLAW_LOCAL", "").lower() in {"1", "true", "yes"}:
        cmd.append("--local")
    if thinking:
        cmd.extend(["--thinking", thinking])

    log_path = path / "logs" / "last_run.log"
    env = ensure_node_env()
    started = time.time()
    meta: dict[str, Any] = {
        "mode": "stream",
        "stream_id": target.id,
        "stream_slug": target.slug,
        "agent_path": str(path),
        "agent_slug": AGENT_SLUG,
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
        if proc.returncode != 0:
            raise RuntimeError(
                f"mfg-social-pulse failed (exit {proc.returncode}). See {log_path}"
            )
        return meta

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
    return meta
