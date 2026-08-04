# pipeline.py
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone

from search.search_engine import search_company_footprint, host_of
from search.denoise import filter_directory_noise, collapse_domain_redundancy, platform_key
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
from export.excel import save_excel


def _make_scorer(company: str, anchor: dict):
    """把 score_leads 包成 search 层需要的 async (leads) -> {url: info} 回调。"""
    async def scorer(leads: list[dict]) -> dict:
        return await score_leads(company, anchor, leads, model=ACTIVE_MODEL)
    return scorer


# 名录类报告里每个平台最多展示几条 URL，其余折叠为计数
MAX_URLS_PER_PLATFORM_IN_REPORT = 3


def _aggregate_by_platform(leads: list[dict]) -> dict[str, list[dict]]:
    """按平台聚合 marketplace_directory 类来源。"""
    by_platform: dict[str, list[dict]] = defaultdict(list)
    for lead in leads:
        by_platform[platform_key(lead["url"])].append(lead)
    for pk in by_platform:
        by_platform[pk].sort(key=lambda r: -(r.get("confidence") or 0))
    return by_platform


def _platform_summary(inventory: list[dict]) -> list[dict]:
    """生成 JSON 用的平台聚合摘要。"""
    mp_leads = [l for l in inventory if l.get("source_type") == "marketplace_directory"]
    by_platform = _aggregate_by_platform(mp_leads)
    rows = []
    for pk, leads in sorted(by_platform.items(), key=lambda x: -len(x[1])):
        rows.append(
            {
                "platform": pk,
                "display_name": pk,
                "count": len(leads),
                "top_urls": [l["url"] for l in leads[:MAX_URLS_PER_PLATFORM_IN_REPORT]],
            }
        )
    return rows


def _select_crawl_subset(results: list[dict], budget: int, per_domain: int) -> list[dict]:
    """
    从完整足迹清单里挑多样化子集做深度抓取：
    1) 尽量每个 source_type 至少 1 条（按各类最高分排序，受 budget 约束）
    2) 在预算内按 weighted_score 填充，且每域名不超过 per_domain 条
    """
    if budget <= 0 or not results:
        return []

    chosen: list[dict] = []
    chosen_urls: set[str] = set()
    per_domain_count: dict[str, int] = defaultdict(int)

    def _try_add(candidate: dict) -> bool:
        url = candidate["url"]
        if url in chosen_urls:
            return False
        domain = host_of(url)
        if per_domain_count[domain] >= per_domain:
            return False
        chosen.append(candidate)
        chosen_urls.add(url)
        per_domain_count[domain] += 1
        return True

    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_type[r.get("source_type") or "other"].append(r)

    type_bests = sorted(
        (max(leads, key=lambda x: x.get("weighted_score", 0)) for leads in by_type.values() if leads),
        key=lambda x: x.get("weighted_score", 0),
        reverse=True,
    )
    for best in type_bests:
        if len(chosen) >= budget:
            break
        _try_add(best)

    for r in results:
        if len(chosen) >= budget:
            break
        _try_add(r)

    return chosen


def _build_result(company: str, anchor: dict, inventory: list[dict], enriched: dict[str, dict]) -> dict:
    """把最终有价值的数据整理成结构化结果(可落盘 JSON)。"""
    sources = []
    for lead in inventory:
        url = lead["url"]
        detail = enriched.get(url)
        page_meta = (detail or {}).get("page_meta") or {}
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
                "bfs_round": lead.get("bfs_round", 0),
                "discovery_path": lead.get("discovery_path", ""),
                "discovery_paths": lead.get("discovery_paths", []),
                "deep_extracted": detail is not None,
                "detail": None if detail is None else {
                    "company_name_on_page": detail.get("company_name_on_page", ""),
                    "profile_or_handle": detail.get("profile_or_handle", ""),
                    "contacts": detail.get("contacts", {"email": "", "phone": ""}),
                    "evidence_snippet": detail.get("evidence_snippet", ""),
                    "is_same_company_confidence": detail.get("is_same_company_confidence", 0.0),
                    "page_links_count": len(page_meta.get("links") or []),
                    "page_links_sample": (page_meta.get("links") or [])[:5],
                    "json_ld_types": page_meta.get("json_ld_types") or [],
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
            "platforms": _platform_summary(inventory),
        },
        "sources": sources,
    }




def _render_lead_line(r: dict, enriched: dict[str, dict]) -> list[str]:
    conf = r.get("confidence") or 0
    own = OWNERSHIP_LABELS.get(r.get("ownership", "unknown"), "未知")
    url = r["url"]
    lines = [f"- [{conf:.0%} · {own}] {url}"]
    if r.get("discovery_path"):
        lines.append(f"    发现路径: {r['discovery_path']}")
    detail = enriched.get(url)
    if detail:
        if detail.get("profile_or_handle"):
            lines.append(f"    账号/主页: {detail['profile_or_handle']}")
        contacts = detail.get("contacts") or {}
        if contacts.get("email") or contacts.get("phone"):
            lines.append(f"    联系方式: {contacts.get('email', '')} {contacts.get('phone', '')}".rstrip())
        if detail.get("evidence_snippet"):
            lines.append(f"    证据: {detail['evidence_snippet']}")
    return lines


def _render_marketplace_section(leads: list[dict], enriched: dict[str, dict]) -> list[str]:
    """交易/名录：按平台聚合展示。"""
    by_platform = _aggregate_by_platform(leads)
    lines = [f"\n## 交易/名录 — 按平台聚合 ({len(leads)} 条，{len(by_platform)} 个平台)"]
    for pk, plats in sorted(by_platform.items(), key=lambda x: -len(x[1])):
        name = pk
        lines.append(f"\n### {name} ({len(plats)} 条)")
        shown = plats[:MAX_URLS_PER_PLATFORM_IN_REPORT]
        for r in shown:
            lines.extend(_render_lead_line(r, enriched))
        rest = len(plats) - len(shown)
        if rest > 0:
            lines.append(f"    … 另有 {rest} 条同平台链接(见 Excel)")
    return lines


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
        if source_type == "marketplace_directory":
            continue  # 单独按平台聚合渲染
        leads = by_source[source_type]
        leads.sort(key=lambda r: (r.get("ownership") != "first_party", -(r.get("confidence") or 0)))
        label = SOURCE_TYPE_LABELS.get(source_type, source_type)
        lines.append(f"\n## {label} ({len(leads)})")
        for r in leads:
            lines.extend(_render_lead_line(r, enriched))

    if "marketplace_directory" in by_source:
        lines.extend(_render_marketplace_section(by_source["marketplace_directory"], enriched))
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
        anchor=anchor,
    )
    if not inventory:
        return "未能检索到与该公司相关的可信来源。"
    inventory, removed = filter_directory_noise(inventory, company, anchor)
    if removed:
        print(f"🧹 名录站去噪: 剔除 {removed} 条无关名录链接，保留 {len(inventory)} 条。")
    inventory, collapsed = collapse_domain_redundancy(inventory, anchor)
    if collapsed:
        print(f"📎 同域折叠: 剔除 {collapsed} 条同质链接，保留 {len(inventory)} 条。")
    print(f"🔗 [Step 1 成功] 足迹清单共 {len(inventory)} 个可信来源。")

    # 只对多样化子集做昂贵的抓取+抽取
    from crawler.registry import crawl_pages

    subset = _select_crawl_subset(inventory, MAX_URLS_TO_CRAWL, MAX_CRAWL_PER_DOMAIN)
    print(f"\n🔍 [Step 2] 选取 {len(subset)} 个来源做深度抓取(每域名≤{MAX_CRAWL_PER_DOMAIN})...")
    urls = [r["url"] for r in subset]
    pages = await crawl_pages(urls)
    pairs = [(u, p) for u, p in zip(urls, pages) if (p.get("markdown") or "").strip()]
    from collections import Counter

    by_method = Counter(
        p.get("crawler_method") or "unknown"
        for _, p in pairs
    )
    failed = len(urls) - len(pairs)
    print(f"📊 [Step 2 成功] 成功抓取 {len(pairs)}/{len(urls)} 个页面。")
    if by_method:
        print(f"   后端分布: {dict(by_method)}")
    if failed:
        print(f"   仍失败 {failed} 个（含 PDF/Trustpilot/Crunchbase 等难站）")

    enriched: dict[str, dict] = {}
    if pairs:
        print(f"\n🤖 [Step 3] 逐页结构化抽取 (Map) [{ACTIVE_MODEL}] ...")
        records = await asyncio.gather(
            *[
                extract_page(company, anchor, u, p["markdown"], model=ACTIVE_MODEL)
                for u, p in pairs
            ]
        )
        for (u, page), rec in zip(pairs, records):
            if rec.get("is_same_company_confidence", 0) >= RELEVANCE_THRESHOLD:
                json_ld_types = sorted(
                    {
                        item.get("@type")
                        for item in (page.get("json_ld") or [])
                        if isinstance(item, dict) and item.get("@type")
                    }
                )
                enriched[u] = {
                    **rec,
                    "page_meta": {
                        "links": page.get("links") or [],
                        "json_ld_types": json_ld_types,
                        "opengraph": page.get("opengraph") or {},
                    },
                }
        print(f"📝 [Step 3 成功] {len(enriched)} 个来源获得深度详情，正在汇总 (Reduce) ...")

    result = _build_result(company, anchor, inventory, enriched)
    excel_path = save_excel(result, OUTPUT_DIR)
    print(f"💾 结构化结果已写入: {excel_path}")

    return _render_report(company, inventory, enriched)
