"""Shared OpenClaw signals collector — one agent, many companies.

Instead of ~/.openclaw/workspace/agents/<company-slug>/ for every target,
we keep a single `signals-collector` workspace and inject company context
per dispatch. Session keys stay per-company for memory isolation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.openclaw_agent import ensure_node_env
from application.scaffold_agent import agents_root, company_slug
from models import Company

COLLECTOR_SLUG = "signals-collector"


def collector_dir() -> Path:
    return agents_root() / COLLECTOR_SLUG


def scaffold_signals_collector(*, vestige_api: str | None = None) -> Path:
    """Create/update the shared collector workspace."""
    path = collector_dir()
    path.mkdir(parents=True, exist_ok=True)
    (path / "tasks").mkdir(exist_ok=True)
    (path / "logs").mkdir(exist_ok=True)

    api = vestige_api or os.getenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")

    agent_md = f"""# Agent: Vestige Signals Collector

## Mission
You are a **shared** competitive-intel collector for Vestige.
Each turn you receive **one company** in `TASK.md` (or the active task file).
Collect **today's incremental signals** for that company only and POST to Vestige.

## Rules
- Work only on the company described in the current task.
- Prefer official / news / filings / reviews over random directories.
- Do not invent URLs. Server dedupes by canonical URL.
- Keep payloads small; put sentiment/themes under `detail`.
- If nothing new: POST empty `items` and say so.

## Ingest
`POST {{api}}/api/companies/{{company_id}}/ingest`

Body:
```json
{{
  "collector": "openclaw:signals-collector",
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

Default API base: `{api}`
"""

    sources = """# Shared collector defaults (overridden per-task with company queries)
enabled:
  - web
  - news
  - rss
  # - sec
  # - trustpilot
"""

    schedule = """# Batch dispatch via Vestige (not one cron per company)
# make dispatch-signals LIMIT=10 TIER=monitoring
# make dispatch-signals LIMIT=20 TIER=target
daily_hint: "30 8 * * *"
timezone: local
"""

    (path / "AGENT.md").write_text(agent_md.replace("{api}", api), encoding="utf-8")
    (path / "sources.yaml").write_text(sources, encoding="utf-8")
    (path / "schedule.yaml").write_text(schedule, encoding="utf-8")
    (path / "collector.json").write_text(
        json.dumps(
            {
                "slug": COLLECTOR_SLUG,
                "vestige_api": api,
                "mode": "shared",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def build_shared_task_message(company: Company, collector_path: Path) -> str:
    api = os.getenv("VESTIGE_API_BASE", "http://127.0.0.1:8001").rstrip("/")
    return f"""# Vestige shared collector task — {company.name}

You are running inside the **shared** signals-collector agent.
Execute the daily routine for **this company only**.

## Context
- Collector brief: `{collector_path / "AGENT.md"}`
- Collector sources: `{collector_path / "sources.yaml"}`

## Company
- Vestige id: `{company.id}`
- Name: {company.name}
- Domain: {company.official_domain or "(none)"}
- Industry: {company.industry or "(none)"}
- Location: {company.location or "(none)"}
- Tier / roles: {company.tier} / {", ".join(company.roles or []) or "(none)"}
- Priority: {company.priority or "(none)"}
- Aliases: {", ".join(company.aliases or []) or "(none)"}

## Required actions
1. Search/collect **today-only** incremental signals for this company.
2. Filter wrong-entity / noise.
3. POST to:
   `POST {api}/api/companies/{company.id}/ingest`
   ```json
   {{
     "collector": "openclaw:signals-collector",
     "items": [{{ "url": "https://...", "title": "...", "snippet": "...", "confidence": 0.7 }}]
   }}
   ```
4. If nothing new, POST `"items": []`.
5. Reply with a short summary: searches tried, inserted/skipped, errors.

Do not work on any other company in this turn.
"""


def write_shared_task(company: Company, collector_path: Path) -> Path:
    slug = company_slug(company)
    task_path = collector_path / "tasks" / f"{slug}.md"
    task_path.write_text(
        build_shared_task_message(company, collector_path), encoding="utf-8"
    )
    # Active pointer for tools that only read TASK.md
    active = collector_path / "TASK.md"
    active.write_text(task_path.read_text(encoding="utf-8"), encoding="utf-8")
    return task_path


def select_dispatch_queue(
    session: Session,
    *,
    limit: int = 10,
    tier: str | None = "monitoring",
    role: str | None = None,
    stale_only: bool = True,
) -> list[Company]:
    """Pick companies that most need a signal pass.

    Order: monitoring before target; never-seen before stale; oldest last_signal first.
    """
    limit = max(1, min(limit, 100))
    stmt = select(Company)
    if tier:
        stmt = stmt.where(Company.tier == tier)
    items = list(session.scalars(stmt))

    if role:
        role_key = role.strip().lower()
        items = [
            c
            for c in items
            if role_key in [r.lower() for r in (c.roles or [])]
        ]

    if stale_only:
        now = datetime.now(timezone.utc)

        def is_stale(company: Company) -> bool:
            last = company.last_signal_at
            if last is None:
                return True
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            return (now - last).total_seconds() > 20 * 3600

        items = [c for c in items if is_stale(c)]

    tier_rank = {"monitoring": 0, "target": 1, "candidate": 2}

    def sort_key(company: Company):
        last = company.last_signal_at
        # None sorts first (never collected)
        ts = last.timestamp() if last is not None else 0.0
        if last is not None and last.tzinfo is None:
            ts = last.replace(tzinfo=timezone.utc).timestamp()
        pri = (company.priority or "").lower()
        pri_rank = 0 if pri in {"critical", "high", "p0", "p1"} else 1
        return (
            tier_rank.get(str(company.tier or "target"), 9),
            pri_rank,
            0 if last is None else 1,
            ts,
        )

    items.sort(key=sort_key)
    return items[:limit]


def run_shared_collector_for_company(
    company: Company,
    *,
    wait: bool = False,
    local: bool = False,
    timeout_seconds: int = 600,
    thinking: str | None = None,
    openclaw_agent: str | None = None,
) -> dict[str, Any]:
    """Dispatch one company through the shared signals-collector workspace."""
    import subprocess
    import time

    from application.openclaw_agent import DEFAULT_OPENCLAW_AGENT, resolve_openclaw_bin

    collector = scaffold_signals_collector()
    task_path = write_shared_task(company, collector)
    agent_id = openclaw_agent or os.getenv("OPENCLAW_AGENT_ID", DEFAULT_OPENCLAW_AGENT)
    slug = company_slug(company)

    cmd = [
        resolve_openclaw_bin(),
        "agent",
        "--agent",
        agent_id,
        "--session-key",
        f"agent:{agent_id}:vestige:signals:{slug}",
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

    log_path = collector / "logs" / f"{slug}.log"
    env = ensure_node_env()
    started = time.time()
    meta: dict[str, Any] = {
        "mode": "shared",
        "collector": COLLECTOR_SLUG,
        "company_id": company.id,
        "company_name": company.name,
        "slug": slug,
        "agent_path": str(collector),
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
                f"shared collector failed for {company.name} "
                f"(exit {proc.returncode}). See {log_path}"
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


def dispatch_signals(
    session: Session,
    *,
    limit: int = 10,
    tier: str | None = "monitoring",
    role: str | None = None,
    stale_only: bool = True,
    wait: bool = False,
    local: bool = False,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Select a queue of companies and start shared-collector turns."""
    scaffold_signals_collector()
    queue = select_dispatch_queue(
        session,
        limit=limit,
        tier=tier,
        role=role,
        stale_only=stale_only,
    )
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for company in queue:
        try:
            meta = run_shared_collector_for_company(
                company,
                wait=wait,
                local=local,
                timeout_seconds=timeout_seconds,
            )
            results.append(meta)
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "company_id": company.id,
                    "company_name": company.name,
                    "error": str(exc),
                }
            )
            if wait:
                # continue batch even if one fails in wait mode
                continue

    return {
        "mode": "shared",
        "collector": COLLECTOR_SLUG,
        "requested": limit,
        "queued": len(queue),
        "started": len(results),
        "failed": len(errors),
        "tier": tier,
        "stale_only": stale_only,
        "results": results,
        "errors": errors,
    }


def use_shared_collector_by_default() -> bool:
    raw = (os.getenv("VESTIGE_SHARED_COLLECTOR") or "1").strip().lower()
    return raw not in {"0", "false", "no", "per-company"}
