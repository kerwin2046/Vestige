# crawler/cloak.py
"""CloakBrowser 子进程抓取（scripts/cloak/cloak-fetch.mjs）。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .main import assemble_page, empty_page

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SCRIPT = _PROJECT_ROOT / "scripts" / "cloak" / "cloak-fetch.mjs"


def resolve_cloak_script() -> Path:
    from config import CLOAK_SCRIPT

    if CLOAK_SCRIPT:
        return Path(CLOAK_SCRIPT).expanduser().resolve()
    return _DEFAULT_SCRIPT


async def fetch(url: str) -> dict[str, Any]:
    from config import CLOAK_TIMEOUT_SEC, MAX_CHARS_PER_PAGE

    script = resolve_cloak_script()
    if not script.is_file():
        return empty_page(url, crawler_method="cloak")

    timeout_ms = int(CLOAK_TIMEOUT_SEC * 1000)
    proc = await asyncio.create_subprocess_exec(
        "node",
        str(script),
        url,
        "--format",
        "html",
        "--timeout",
        str(timeout_ms),
        "--no-rate-limit",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, _stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=CLOAK_TIMEOUT_SEC + 5,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return empty_page(url, crawler_method="cloak")

    if proc.returncode != 0:
        return empty_page(url, crawler_method="cloak")

    line = (stdout or b"").decode(errors="replace").strip().splitlines()
    if not line:
        return empty_page(url, crawler_method="cloak")

    try:
        payload = json.loads(line[-1])
    except json.JSONDecodeError:
        return empty_page(url, crawler_method="cloak")

    html = payload.get("content") or ""
    title = payload.get("title") or ""
    return assemble_page(
        url,
        html=html,
        markdown="",
        metadata={"title": title},
        crawler_method="cloak",
        max_chars=MAX_CHARS_PER_PAGE,
    )
