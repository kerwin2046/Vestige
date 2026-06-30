# pipeline.py
import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from search.search_engine import search_company_footprint, host_of
from crawlers.scraper import fetch_pages_content
from llm.extractor import score_leads, extract_page, SOURCE_TYPE_LABELS, OWNERSHIP_LABELS
from config import (
    ACTIVE_MODEL,
    COMPANY_ANCHOR,
    RELEVANCE_THRESHOLD,
    MAX_URLS_TO_CRAWL,
    MAX_CRAWL_PER_DOMAIN,
    SEARCH_BACKEND,
    OUTPUT_DIR,
)


def _make_scorer(company: str, anchor: dict):
    """把 score_leads 包成 search 层需要的 async (leads) -> {url: info} 回调。"""
    async def scorer(leads: list[dict]) -> dict:
        return await score_leads(company, anchor, leads, model=ACTIVE_MODEL)
    return scorer


def _select_crawl_subset(results: list[dict], budget: int, per_domain: int) -> list[dict]:
    """从完整足迹清单里挑“多样化”子集做深度抓取：按加权得分优先，但每个域名最多 per_domain 条。"""
    chosen, per_domain_count = [], defaultdict(int)
    for r in results:  # results 已按 weighted_score 降序
        domain = host_of(r["url"])
        if per_domain_count[domain] >= per_domain:
            continue
        chosen.append(r)
        per_domain_count[domain] += 1
        if len(chosen) >= budget:
            break
    return chosen


def _build_result(company: str, anchor: dict, inventory: list[dict], enriched: dict[str, dict]) -> dict:
    """把最终有价值的数据整理成结构化结果(可落盘 JSON)。"""
    sources = []
    for lead in inventory:
        url = lead["url"]
        detail = enriched.get(url)
        sources.append(
            {
                "url": url,
                "domain": host_of(url),
                "source_type": lead.get("source_type") or "other",
                "ownership": lead.get("ownership") or "unknown",
                "confidence": round(lead.get("confidence") or 0.0, 3),
                "title": lead.get("title", ""),
                "snippet": lead.get("snippet", ""),
                "score": round(lead.get("score", 0.0), 3),
                "weighted_score": lead.get("weighted_score", 0.0),
                "matched_queries": lead.get("matched_queries", []),
                "engines": lead.get("engines", []),
                "deep_extracted": detail is not None,
                "detail": None if detail is None else {
                    "company_name_on_page": detail.get("company_name_on_page", ""),
                    "profile_or_handle": detail.get("profile_or_handle", ""),
                    "contacts": detail.get("contacts", {"email": "", "phone": ""}),
                    "evidence_snippet": detail.get("evidence_snippet", ""),
                    "is_same_company_confidence": detail.get("is_same_company_confidence", 0.0),
                },
            }
        )

    return {
        "company": company,
        "anchor": anchor,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "search_backend": SEARCH_BACKEND,
        "summary": {
            "total_sources": len(sources),
            "deep_extracted": len(enriched),
            "by_source_type": dict(Counter(s["source_type"] for s in sources)),
            "by_ownership": dict(Counter(s["ownership"] for s in sources)),
        },
        "sources": sources,
    }


def _save_json(result: dict) -> Path:
    """把结构化结果写入 OUTPUT_DIR/<公司名安全化>.json，返回文件路径。"""
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", result["company"]).strip("_") or "company"
    path = out_dir / f"{safe}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _render_report(company: str, inventory: list[dict], enriched: dict[str, dict]) -> str:
    """
    Reduce：报告主体是“全量来源清单”(按 source_type 分组，不砍)，
    其中做了深度抽取的来源额外附上联系方式/证据。
    enriched: {url: extract_page 结果}
    """
    if not inventory:
        return "未发现该公司的可信来源。"

    by_source: dict[str, list[dict]] = defaultdict(list)
    for lead in inventory:
        by_source[lead.get("source_type") or "other"].append(lead)

    lines = [
        f"# 公司「{company}」全网足迹清单",
        f"\n共发现 {len(inventory)} 个可信来源，其中 {len(enriched)} 个做了深度抽取。按来源类型(source_type)分组：",
    ]
    for source_type in sorted(by_source, key=lambda s: -len(by_source[s])):
        leads = by_source[source_type]
        leads.sort(key=lambda r: (r.get("ownership") != "first_party", -(r.get("confidence") or 0)))
        label = SOURCE_TYPE_LABELS.get(source_type, source_type)
        lines.append(f"\n## {label} ({len(leads)})")
        for r in leads:
            conf = r.get("confidence") or 0
            own = OWNERSHIP_LABELS.get(r.get("ownership", "unknown"), "未知")
            url = r["url"]
            lines.append(f"- [{conf:.0%} · {own}] {url}")
            detail = enriched.get(url)
            if detail:
                if detail.get("profile_or_handle"):
                    lines.append(f"    账号/主页: {detail['profile_or_handle']}")
                contacts = detail.get("contacts") or {}
                if contacts.get("email") or contacts.get("phone"):
                    lines.append(f"    联系方式: {contacts.get('email', '')} {contacts.get('phone', '')}".rstrip())
                if detail.get("evidence_snippet"):
                    lines.append(f"    证据: {detail['evidence_snippet']}")
    return "\n".join(lines)


async def run_rag_pipeline(company: str | None = None) -> str:
    """
    公司全网足迹发现编排：
    多轮 BFS(+消歧门控) -> 全量足迹清单 -> 对多样化子集 Crawl4AI 抓取 + 逐页抽取 -> 归类报告
    """
    anchor = COMPANY_ANCHOR
    company = company or anchor.get("name", "")

    print(f"\n📡 [Step 1] 多轮 BFS 检索 + 身份消歧: '{company}' ...")
    inventory = await search_company_footprint(
        company,
        relevance_scorer=_make_scorer(company, anchor),
        relevance_threshold=RELEVANCE_THRESHOLD,
        drop_below_threshold=True,  # 仍剔除“不是这家公司”的同名噪声，但不限数量
    )
    if not inventory:
        return "未能检索到与该公司相关的可信来源。"
    print(f"🔗 [Step 1 成功] 足迹清单共 {len(inventory)} 个可信来源(完整保留)。")

    # 只对多样化子集做昂贵的抓取+抽取
    subset = _select_crawl_subset(inventory, MAX_URLS_TO_CRAWL, MAX_CRAWL_PER_DOMAIN)
    print(f"\n🔍 [Step 2] 选取 {len(subset)} 个来源做深度抓取(每域名≤{MAX_CRAWL_PER_DOMAIN})...")
    urls = [r["url"] for r in subset]
    pages_content = await fetch_pages_content(urls)
    pairs = [(u, c) for u, c in zip(urls, pages_content) if c and c.strip()]
    print(f"📊 [Step 2 成功] 成功抓取 {len(pairs)} 个页面。")

    enriched: dict[str, dict] = {}
    if pairs:
        print(f"\n🤖 [Step 3] 逐页结构化抽取 (Map) [{ACTIVE_MODEL}] ...")
        records = await asyncio.gather(
            *[extract_page(company, anchor, u, c, model=ACTIVE_MODEL) for u, c in pairs]
        )
        for (u, _), rec in zip(pairs, records):
            if rec.get("is_same_company_confidence", 0) >= RELEVANCE_THRESHOLD:
                enriched[u] = rec
        print(f"📝 [Step 3 成功] {len(enriched)} 个来源获得深度详情，正在汇总 (Reduce) ...")

    result = _build_result(company, anchor, inventory, enriched)
    json_path = _save_json(result)
    print(f"💾 结构化结果已写入: {json_path}")

    return _render_report(company, inventory, enriched)
