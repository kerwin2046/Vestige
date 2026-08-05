# search/search_engine.py
import asyncio
from collections import defaultdict
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from config import (
    MAX_RESULTS_PER_QUERY,
    DISCOVERY_QUERY_TEMPLATES,
    FOCUSED_QUERY_TEMPLATES,
    MAX_BFS_ROUNDS,
    MAX_DOMAINS_PER_ROUND,
    MAX_MARKETPLACE_DOMAINS_PER_ROUND,
    MAX_TOTAL_DOMAINS_TO_EXPAND,
    DOMAIN_EXPANSION_BLOCKLIST,
    RELEVANCE_THRESHOLD,
    SCORE_LEADS_BFS_ABORT_UNSCORED_RATIO,
)
from search.web.registry import get_search_client
from search.denoise import domain_is_marketplace, host_of, is_owned_domain

# 常见的跟踪类查询参数，规范化时去掉，避免同一页面因参数不同被当成不同 URL
_TRACKING_PARAMS = {
    "fbclid", "gclid", "msclkid", "yclid", "ref", "ref_src", "spm",
}


def canonicalize_url(url: str) -> str:
    """
    规范化 URL，用于去重：
    - scheme/host 小写
    - 去掉 fragment(#...)
    - 去掉 utm_* 及常见跟踪参数
    - 去掉默认端口和末尾多余的 '/'
    """
    try:
        parts = urlsplit(url.strip())
    except Exception:
        return url.strip()

    scheme = parts.scheme.lower() or "http"
    netloc = parts.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    kept_query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(kept_query)
    path = parts.path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, query, ""))


def host_of(url: str) -> str:
    """提取 URL 的主机名(含子域，去掉端口和 www.)，用作来源域名。"""
    try:
        netloc = urlsplit(url).netloc.lower().split(":")[0]
    except Exception:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


async def _run_queries(backend, queries: list[str], max_results: int) -> list[list[dict]]:
    """通过检索后端并发执行一批查询，返回与 queries 等长的结果列表。
    后端内部已做限流(并发上限+最小间隔)，避免触发上游引擎的反爬。
    """
    tasks = [backend.search(q, max_results) for q in queries]
    return await asyncio.gather(*tasks)


def _format_discovery_path(bfs_round: int, query: str, rank: int, engine: str) -> str:
    phase = "discovery" if bfs_round == 0 else f"focused-r{bfs_round}"
    engine_label = engine or "unknown"
    return f"search:{phase} | query={query!r} | rank={rank + 1} | engine={engine_label}"


def _merge_into(
    merged: dict,
    queries: list[str],
    per_query_results: list[list[dict]],
    bfs_round: int = 0,
) -> dict:
    """
    把一批查询结果按规范化 URL 合并进累加器 merged，并累加得分。
    一个 URL 被越多查询命中、在各查询里排名越靠前，得分越高。
    首次命中时记录 bfs_round 与 discovery_paths（可解释「怎么发现的」）。
    """
    for query, results in zip(queries, per_query_results):
        for rank, item in enumerate(results):
            canon = canonicalize_url(item["url"])
            rank_score = 1.0 / (rank + 1)
            path = _format_discovery_path(bfs_round, query, rank, item.get("engine", ""))

            entry = merged.get(canon)
            if entry is None:
                entry = {
                    "url": item["url"],
                    "canonical_url": canon,
                    "title": item["title"],
                    "snippet": item["snippet"],
                    "engines": set(),
                    "matched_queries": set(),
                    "discovery_paths": [path],
                    "bfs_round": bfs_round,
                    "first_query": query,
                    "score": 0.0,
                    "confidence": None,   # 消歧置信度，None 表示尚未打分
                    "source_type": "",    # 由消歧/抽取阶段填充
                    "ownership": "",      # 由消歧/抽取阶段填充
                }
                merged[canon] = entry
            else:
                paths = entry.setdefault("discovery_paths", [])
                if path not in paths:
                    paths.append(path)
                if bfs_round < entry.get("bfs_round", bfs_round):
                    entry["bfs_round"] = bfs_round
                    entry["first_query"] = query

            entry["score"] += rank_score
            entry["matched_queries"].add(query)
            if item.get("engine"):
                entry["engines"].add(item["engine"])
            if not entry["title"] and item.get("title"):
                entry["title"] = item["title"]
            if not entry["snippet"] and item.get("snippet"):
                entry["snippet"] = item["snippet"]
    return merged


def _effective_confidence(entry: dict) -> float:
    """未打分(None)时按中性 1.0 处理，仅用于无 scorer 时的排序退化。"""
    conf = entry.get("confidence")
    return 1.0 if conf is None else conf


def _passes_relevance_gate(entry: dict, threshold: float) -> bool:
    """BFS / 最终过滤：必须已评分且达到阈值。"""
    conf = entry.get("confidence")
    return conf is not None and conf >= threshold


def _weighted_score(entry: dict) -> float:
    """最终排序用：原始检索得分 × 消歧置信度（未评分按 0 处理）。"""
    conf = entry.get("confidence")
    multiplier = 0.0 if conf is None else conf
    return entry["score"] * multiplier


def _domain_is_marketplace(merged: dict, domain: str) -> bool:
    """域名是否以名录/聚合为主（由流程数据动态判定，非静态名单）。"""
    return domain_is_marketplace(merged, domain)


def _expansion_blocklist(anchor: dict | None) -> set[str]:
    blocked = set(DOMAIN_EXPANSION_BLOCKLIST)
    if not anchor:
        return blocked
    official = (anchor.get("official_domain") or "").lower().strip()
    if official:
        blocked.add(official)
    return blocked


def _rank_domains(
    merged: dict,
    exclude: set[str],
    limit: int,
    threshold: float,
    max_marketplace: int = MAX_MARKETPLACE_DOMAINS_PER_ROUND,
    anchor: dict | None = None,
    blocklist: set[str] | None = None,
) -> list[str]:
    """
    选出最有价值、尚未扩展过的来源域名，构成 BFS frontier。
    名录站域名每轮最多占 max_marketplace 个名额，其余留给展会/协会/社媒等。
    """
    if limit <= 0:
        return []
    blocked = blocklist if blocklist is not None else _expansion_blocklist(anchor)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for entry in merged.values():
        by_domain[host_of(entry["url"])].append(entry)

    domain_scores: dict[str, float] = {}
    domain_passes_gate: dict[str, bool] = {}
    for entry in merged.values():
        domain = host_of(entry["url"])
        if not domain or domain in blocked or domain in exclude:
            continue
        if anchor and is_owned_domain(domain, by_domain.get(domain, []), anchor):
            continue
        if entry.get("confidence") is not None:
            domain_scores[domain] = domain_scores.get(domain, 0.0) + _weighted_score(entry)
        if _passes_relevance_gate(entry, threshold):
            domain_passes_gate[domain] = True

    mp: list[tuple[str, float]] = []
    other: list[tuple[str, float]] = []
    for d, s in domain_scores.items():
        if not domain_passes_gate.get(d, False):
            continue
        if _domain_is_marketplace(merged, d):
            mp.append((d, s))
        else:
            other.append((d, s))
    mp.sort(key=lambda x: x[1], reverse=True)
    other.sort(key=lambda x: x[1], reverse=True)

    # Never exceed `limit`. Taking mp[:max_marketplace] first can make
    # remain negative; in Python other[:-1] then returns almost everything.
    mp_budget = min(max(0, max_marketplace), limit)
    picked = [d for d, _ in mp[:mp_budget]]
    remain = limit - len(picked)
    if remain > 0:
        picked.extend(d for d, _ in other[:remain])
    if remain > 0 and len(picked) < limit:
        extra = limit - len(picked)
        already = set(picked)
        for d, _ in mp[mp_budget:]:
            if d not in already:
                picked.append(d)
                extra -= 1
                if extra <= 0:
                    break
    return picked


async def _score_new_leads(merged: dict, relevance_scorer) -> tuple[int, int]:
    """
    对尚未打分(confidence is None)的线索调用 scorer。
    返回 (本批获得评分数, 本批待评分数)。
    未获评分的线索保持 confidence=None。
    """
    if relevance_scorer is None:
        return 0, 0
    pending = [e for e in merged.values() if e["confidence"] is None]
    if not pending:
        return 0, 0
    print(f"   ↳ 消歧打分 (LLM): 对 {len(pending)} 条新线索评估归属置信度 ...")
    leads = [{"url": e["url"], "title": e["title"], "snippet": e["snippet"]} for e in pending]
    scores = await relevance_scorer(leads)
    scored = 0
    unscored = 0
    for entry in pending:
        info = scores.get(entry["url"])
        if info is None:
            unscored += 1
            continue
        scored += 1
        entry["confidence"] = info.get("confidence", 0.5)
        if info.get("source_type"):
            entry["source_type"] = info["source_type"]
        if info.get("ownership"):
            entry["ownership"] = info["ownership"]
    if unscored:
        print(
            f"   ↳ 消歧完成: {scored}/{len(pending)} 条获得评分，"
            f"{unscored} 条未评分(保持 confidence=None，不参与 BFS 扩展)"
        )
    else:
        print(f"   ↳ 消歧完成: {scored}/{len(pending)} 条获得评分")
    return scored, len(pending)


def _bfs_should_abort(merged: dict, scored: int, pending: int) -> bool:
    """消歧失败或未覆盖过多时停止 BFS，避免盲扩。"""
    if pending == 0:
        return False
    if scored == 0:
        print("   ↳ 消歧完全失败(0 条获得评分)，停止 BFS 扩展。")
        return True
    unscored_ratio = (pending - scored) / pending
    if unscored_ratio > SCORE_LEADS_BFS_ABORT_UNSCORED_RATIO:
        print(
            f"   ↳ 消歧未完成({pending - scored}/{pending} 未评分，"
            f">{SCORE_LEADS_BFS_ABORT_UNSCORED_RATIO:.0%})，停止 BFS 扩展。"
        )
        return True
    return False


def _finalize(merged: dict, max_urls, threshold: float, drop_below_threshold: bool) -> list[dict]:
    entries = list(merged.values())
    total = len(entries)
    if drop_below_threshold:
        entries = [e for e in entries if _passes_relevance_gate(e, threshold)]
        passed = len(entries)
        if total >= 30 and passed <= max(2, total // 20):
            print(
                f"   ↳ 置信度过滤(≥{threshold}): {passed}/{total} 条通过。"
                f"短名/高同名歧义时请完善 COMPANY_ANCHOR(全称、官网、别名、地区)。"
            )
    ranked = sorted(entries, key=_weighted_score, reverse=True)
    for entry in ranked:
        entry["engines"] = sorted(entry["engines"])
        entry["matched_queries"] = sorted(entry["matched_queries"])
        paths = entry.get("discovery_paths") or []
        entry["discovery_path"] = paths[0] if paths else ""
        entry["bfs_round"] = entry.get("bfs_round", 0)
        entry["weighted_score"] = round(_weighted_score(entry), 3)
    # max_urls 为 None 表示不截断（足迹清单要完整，越多越好）
    return ranked if max_urls is None else ranked[:max_urls]


async def search_company_footprint(
    company: str,
    max_results_per_query: int = MAX_RESULTS_PER_QUERY,
    max_urls=None,  # None = 返回全部过门来源（足迹清单不设上限）
    max_rounds: int = MAX_BFS_ROUNDS,
    max_domains_per_round: int = MAX_DOMAINS_PER_ROUND,
    max_total_domains: int = MAX_TOTAL_DOMAINS_TO_EXPAND,
    expand_sources: bool = True,
    relevance_scorer=None,
    relevance_threshold: float = RELEVANCE_THRESHOLD,
    drop_below_threshold: bool = False,
    backend=None,
    anchor: dict | None = None,
) -> list[dict]:
    """
    多轮 BFS 公司足迹检索（Source Discovery）+ 身份消歧门控。

    Round 0 — Discovery(广度)：用少量高覆盖查询发现“有哪些来源在提这家公司”。
    Round 1..N — Focused(深度)：每轮对新线索做消歧打分，再从“已发现但未扩展、且置信度过门”
        的域名里 best-first 选取若干个深挖；深挖暴露的新域名进入下一轮 frontier。

    relevance_scorer: 可选的异步回调 async (leads: list[dict]) -> {url: {confidence, platform_type, reason}}。
        注入它即可启用消歧门控（低置信度域名不扩展、低置信度线索沉底）；为 None 时退化为纯检索。

    刹车机制：max_rounds / max_domains_per_round / max_total_domains / 已扩展集合 / blocklist / 置信度门控。

    返回按“置信度加权得分”降序、去重后的结构化结果，每项含:
        url / canonical_url / title / snippet / engines / score / weighted_score /
        confidence / platform_type / matched_queries
    """
    merged: dict = {}
    expanded: set[str] = set()  # 已经做过 site: 深挖的域名，避免重复扩展
    expansion_blocklist = _expansion_blocklist(anchor)
    if backend is None:
        backend = get_search_client()
    print(f"   ↳ 使用检索后端: {backend.name}")

    # ---------- Round 0: Discovery ----------
    discovery_queries = [t.format(company=company) for t in DISCOVERY_QUERY_TEMPLATES]
    print(f"   ↳ Round 0 (Discovery): {len(discovery_queries)} 条广度查询(限流并发) ...")
    r0 = await _run_queries(backend, discovery_queries, max_results_per_query)
    _merge_into(merged, discovery_queries, r0, bfs_round=0)
    print(f"   ↳ Round 0 完成: 去重后累计 {len(merged)} 条线索")
    scored_r0, pending_r0 = await _score_new_leads(merged, relevance_scorer)

    if not expand_sources:
        return _finalize(merged, max_urls, relevance_threshold, drop_below_threshold)

    if relevance_scorer is not None and _bfs_should_abort(merged, scored_r0, pending_r0):
        return _finalize(merged, max_urls, relevance_threshold, drop_below_threshold)

    # ---------- Round 1..N: BFS Focused ----------
    for round_i in range(1, max_rounds + 1):
        remaining_budget = max_total_domains - len(expanded)
        if remaining_budget <= 0:
            print(f"   ↳ 已达全局域名预算 ({max_total_domains})，停止扩展。")
            break

        k = min(max_domains_per_round, remaining_budget)
        # frontier = 已发现但未扩展、且置信度过门的域名，按加权得分 best-first 选 top-k
        candidates = _rank_domains(
            merged,
            exclude=expanded,
            limit=k,
            threshold=relevance_threshold,
            anchor=anchor,
            blocklist=expansion_blocklist,
        )
        if not candidates:
            print(f"   ↳ Round {round_i}: 无满足置信度的新来源域名，BFS 收敛，停止。")
            break

        print(f"   ↳ Round {round_i}: 扩展 {len(candidates)} 个新来源: {', '.join(candidates)}")
        focused_queries = [
            t.format(site=domain, company=company)
            for domain in candidates
            for t in FOCUSED_QUERY_TEMPLATES
        ]
        print(f"   ↳ Round {round_i}: 执行 {len(focused_queries)} 条定向查询(限流并发，预计较慢) ...")
        results = await _run_queries(backend, focused_queries, max_results_per_query)
        _merge_into(merged, focused_queries, results, bfs_round=round_i)
        print(f"   ↳ Round {round_i}: 去重后累计 {len(merged)} 条线索")
        scored_rn, pending_rn = await _score_new_leads(merged, relevance_scorer)
        if relevance_scorer is not None and _bfs_should_abort(merged, scored_rn, pending_rn):
            break
        expanded.update(candidates)

    print(f"   ↳ BFS 结束：累计扩展 {len(expanded)} 个来源域名，去重后共 {len(merged)} 条线索。")
    return _finalize(merged, max_urls, relevance_threshold, drop_below_threshold)
