"""Scaffold per-company OpenClaw agents that ingest into Vestige."""

from __future__ import annotations

import os
import re
from pathlib import Path

from models import Company

DEFAULT_AGENTS_ROOT = Path.home() / ".openclaw" / "workspace" / "agents"


def agents_root() -> Path:
    return Path(os.getenv("OPENCLAW_AGENTS_DIR", DEFAULT_AGENTS_ROOT)).expanduser()


def company_slug(company: Company) -> str:
    base = (company.official_domain or company.name or "company").strip().lower()
    base = base.removeprefix("www.")
    if "." in base and " " not in base and not any(ord(ch) > 127 for ch in base):
        base = re.sub(r"\.[a-z]{2,}$", "", base)
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", base, flags=re.IGNORECASE).strip("-")
    if not slug or slug == "company":
        slug = f"company-{company.id[:8]}"
    return slug.lower() if slug.isascii() else slug


def scaffold_company_agent(
    company: Company,
    *,
    vestige_api: str | None = None,
) -> Path:
    """Create ~/.openclaw/workspace/agents/<slug>/ for daily signal collection."""
    root = agents_root()
    slug = company_slug(company)
    path = root / slug
    path.mkdir(parents=True, exist_ok=True)

    api = vestige_api or os.getenv("VESTIGE_API_BASE", "http://127.0.0.1:8001")
    aliases = ", ".join(company.aliases or []) or "(none)"

    agent_md = f"""# Agent: {company.name}

## Mission
Daily competitive / web signals for **{company.name}**.
Write results into Vestige SQLite via ingest API (path A).

## Company
- id: `{company.id}`
- domain: `{company.official_domain or "-"}`
- aliases: {aliases}

## Daily routine
1. Read `sources.yaml` and collect new URLs/snippets for this company only.
2. Filter noise / wrong-entity hits.
3. POST items to Vestige:
   `POST {api}/api/companies/{company.id}/ingest`
4. Report inserted/skipped counts.

## Rules
- Prefer incremental sources (reviews, RSS, filings, official channels).
- Do not invent URLs. Dedup is server-side by canonical URL.
- Keep payloads small; put sentiment/themes under `detail`.
"""

    schedule = """# OpenClaw / cron hint
daily: "30 8 * * *"   # 08:30 local
weekly: "0 10 * * 0"  # Sunday 10:00 — deeper pass
timezone: local
"""

    sources = f"""# Enabled collectors for {company.name}
enabled:
  - trustpilot
  - rss
  - sec
  # - youtube
  # - exa

queries:
  - '"{company.name}"'
  - 'site:{company.official_domain or "example.com"}'
"""

    run_daily = f"""#!/usr/bin/env bash
# Example daily ingest for {company.name}
# Replace the JSON body with real collector output.
set -euo pipefail
API="${{VESTIGE_API_BASE:-{api}}}"
COMPANY_ID="{company.id}"

curl -sS -X POST "$API/api/companies/$COMPANY_ID/ingest" \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "collector": "openclaw:{slug}",
    "items": []
  }}' | python3 -m json.tool
"""

    (path / "AGENT.md").write_text(agent_md, encoding="utf-8")
    (path / "schedule.yaml").write_text(schedule, encoding="utf-8")
    (path / "sources.yaml").write_text(sources, encoding="utf-8")
    run_path = path / "run_daily.sh"
    run_path.write_text(run_daily, encoding="utf-8")
    run_path.chmod(run_path.stat().st_mode | 0o111)

    meta = {
        "company_id": company.id,
        "name": company.name,
        "domain": company.official_domain,
        "slug": slug,
        "vestige_api": api,
    }
    import json

    (path / "company.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path
