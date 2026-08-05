"""Multi-lane discovery orchestration for a single Vestige run.

Lanes (v1):
  - footprint: existing SERP BFS + crawl pipeline
  - channels: targeted site: searches against Vestige channel domains
  - owned: ensure official domain is represented when present

Empty overall inventory fails the run with a clear error (no fake success).
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.run_company import run_company
from config import SEARCH_BACKEND
from models import Channel
from search.web.registry import get_search_client


DEFAULT_LANES = ["footprint", "channels", "owned"]


def _host(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in sources:
        key = (item.get("canonical_url") or item.get("url") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def _lane_footprint(
    *,
    company: dict[str, Any],
    settings: dict[str, Any],
    output_dir: str,
) -> dict[str, Any]:
    try:
        outcome = await run_company(
            name=company["name"],
            official_domain=company.get("official_domain") or "",
            industry=company.get("industry") or "",
            location=company.get("location") or "",
            aliases=list(company.get("aliases") or []),
            settings=settings,
            output_dir=output_dir,
            write_excel=True,
        )
        sources = (outcome.get("result") or {}).get("sources") or []
        report = outcome.get("report") or ""
        empty_reason = None
        if not sources:
            empty_reason = report or "footprint search returned no inventory"
        return {
            "lane": "footprint",
            "status": "ok" if sources else "empty",
            "sources": sources,
            "export_path": outcome.get("export_path"),
            "error": empty_reason,
        }
    except Exception as exc:
        return {
            "lane": "footprint",
            "status": "error",
            "sources": [],
            "export_path": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _pick_channels(session: Session, *, industry: str, limit: int = 25) -> list[Channel]:
    stmt = select(Channel).order_by(Channel.score.desc(), Channel.name.asc())
    items = list(session.scalars(stmt.limit(400)))
    if not items:
        return []

    industry_key = (industry or "").strip().lower()
    preferred: list[Channel] = []
    rest: list[Channel] = []
    for ch in items:
        if not ch.domain:
            continue
        # Prefer associations with member directories and industry matches
        score_boost = 0
        if ch.has_member_directory:
            score_boost += 2
        if industry_key and industry_key in (ch.industry or "").lower():
            score_boost += 3
        if ch.kind == "platform" and ch.score and ch.score >= 0.8:
            score_boost += 1
        bucket = preferred if score_boost >= 2 else rest
        bucket.append(ch)

    ordered = preferred + rest
    return ordered[:limit]


async def _lane_channels(
    session: Session,
    *,
    company: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    channels = _pick_channels(
        session,
        industry=company.get("industry") or "",
        limit=int(settings.get("channel_limit") or 25),
    )
    if not channels:
        return {
            "lane": "channels",
            "status": "empty",
            "sources": [],
            "error": "no channels in Vestige DB (run make import-b2b)",
            "meta": {"channel_count": 0, "hit_count": 0},
        }

    backend_name = settings.get("search_backend") or SEARCH_BACKEND
    backend = get_search_client(primary=backend_name)
    company_name = company["name"]
    queries = [
        (f'"{company_name}" site:{ch.domain}', ch)
        for ch in channels
        if ch.domain
    ]

    # Bound concurrency via backend throttle; gather in chunks
    hits: list[dict[str, Any]] = []
    errors: list[str] = []
    chunk_size = 8
    for i in range(0, len(queries), chunk_size):
        chunk = queries[i : i + chunk_size]
        try:
            results = await asyncio.gather(
                *[backend.search(q, 5) for q, _ in chunk],
                return_exceptions=True,
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        for (q, ch), result in zip(chunk, results):
            if isinstance(result, Exception):
                errors.append(f"{q}: {type(result).__name__}: {result}")
                continue
            domain = ch.domain
            source_type = (
                "marketplace_directory" if ch.kind == "platform" else "public_record"
            )
            for hit in result or []:
                url = (hit.get("url") or "").strip()
                if not url:
                    continue
                hits.append(
                    {
                        "url": url,
                        "canonical_url": url,
                        "domain": _host(url) or domain,
                        "source_type": source_type,
                        "ownership": "third_party",
                        "confidence": 0.55,
                        "title": hit.get("title") or "",
                        "snippet": hit.get("snippet") or hit.get("body") or "",
                        "discovery_path": f"channel:site | query={q!r}",
                        "bfs_round": 0,
                        "detail": {
                            "lane": "channels",
                            "channel_id": ch.id,
                            "channel_name": ch.name,
                            "channel_kind": ch.kind,
                            "channel_domain": domain,
                            "engines": hit.get("engines") or [],
                        },
                    }
                )

    # If search is broken, still surface top channel seeds so the run isn't blank.
    seed_sources: list[dict[str, Any]] = []
    if not hits:
        for ch in channels[:12]:
            url = (ch.url or "").strip() or f"https://{ch.domain}"
            seed_sources.append(
                {
                    "url": url,
                    "canonical_url": url,
                    "domain": ch.domain,
                    "source_type": "marketplace_directory"
                    if ch.kind == "platform"
                    else "public_record",
                    "ownership": "third_party",
                    "confidence": 0.25,
                    "title": f"{company_name} · channel seed · {ch.name}",
                    "snippet": f"Targeted channel for follow-up search on {ch.domain}",
                    "discovery_path": "channel:seed",
                    "bfs_round": 0,
                    "detail": {
                        "lane": "channels",
                        "seed": True,
                        "channel_id": ch.id,
                        "channel_name": ch.name,
                        "channel_kind": ch.kind,
                        "reason": "search returned no site: hits; seeded channel for agent/manual follow-up",
                    },
                }
            )

    sources = _dedupe_sources(hits or seed_sources)
    status = "ok" if hits else ("seeded" if seed_sources else "empty")
    error = None
    if status == "seeded":
        error = "channel site: search returned 0 hits (engine limited?); seeded channel targets"
    elif status == "empty":
        error = "; ".join(errors[:3]) if errors else "channels lane produced no sources"

    return {
        "lane": "channels",
        "status": status,
        "sources": sources,
        "error": error,
        "meta": {
            "channel_count": len(channels),
            "query_count": len(queries),
            "hit_count": len(hits),
            "seed_count": len(seed_sources),
            "errors": errors[:5],
        },
    }


async def _lane_owned(*, company: dict[str, Any]) -> dict[str, Any]:
    domain = (company.get("official_domain") or "").strip().lower().removeprefix("www.")
    if not domain:
        return {
            "lane": "owned",
            "status": "skipped",
            "sources": [],
            "error": "no official_domain",
        }
    url = f"https://{domain}"
    return {
        "lane": "owned",
        "status": "ok",
        "sources": [
            {
                "url": url,
                "canonical_url": url,
                "domain": domain,
                "source_type": "owned",
                "ownership": "first_party",
                "confidence": 0.9,
                "title": f"{company['name']} official site",
                "snippet": "Seeded from company official_domain",
                "discovery_path": "owned:anchor",
                "bfs_round": 0,
                "detail": {"lane": "owned"},
            }
        ],
        "error": None,
    }


async def orchestrate_run(
    session: Session,
    *,
    company: dict[str, Any],
    settings: dict[str, Any] | None,
    output_dir: str,
) -> dict[str, Any]:
    settings = dict(settings or {})
    lanes = list(settings.get("lanes") or DEFAULT_LANES)

    lane_results: list[dict[str, Any]] = []
    if "footprint" in lanes:
        lane_results.append(
            await _lane_footprint(
                company=company, settings=settings, output_dir=output_dir
            )
        )
    if "channels" in lanes:
        lane_results.append(
            await _lane_channels(session, company=company, settings=settings)
        )
    if "owned" in lanes:
        lane_results.append(await _lane_owned(company=company))

    merged: list[dict[str, Any]] = []
    export_path = None
    for lane in lane_results:
        merged.extend(lane.get("sources") or [])
        if lane.get("lane") == "footprint" and lane.get("export_path"):
            export_path = lane["export_path"]

    sources = _dedupe_sources(merged)
    lane_summary = {
        lane["lane"]: {
            "status": lane.get("status"),
            "source_count": len(lane.get("sources") or []),
            "error": lane.get("error"),
            "meta": lane.get("meta"),
        }
        for lane in lane_results
    }

    errors = [
        f"{k}: {v.get('error') or v.get('status')}"
        for k, v in lane_summary.items()
    ]

    footprint_ok = lane_summary.get("footprint", {}).get("status") == "ok"
    channels_ok = lane_summary.get("channels", {}).get("status") == "ok"
    if not footprint_ok and not channels_ok:
        raise RuntimeError(
            "All discovery lanes returned no usable hits "
            "(owned/channel seeds alone are not enough). "
            + "; ".join(errors)
        )

    warning = None
    if lane_summary.get("footprint", {}).get("status") in {"empty", "error"}:
        warning = (
            f"Footprint lane weak/failed ({lane_summary['footprint'].get('error')}); "
            "results came from other lanes."
        )

    return {
        "sources": sources,
        "export_path": export_path,
        "lanes": lane_summary,
        "warning": warning,
    }
