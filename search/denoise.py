# search/denoise.py
"""
名录站去噪（流程驱动、动态判定）：

不维护静态「名录站名单」。在流水线运行时根据：
  1) LLM 标注的 source_type == marketplace_directory
  2) 域名行为：同域多条线索但多数 URL/标题不含公司 token → 视为聚合站

对需要去噪的线索，要求 URL/title/snippet 命中公司身份 token，否则剔除。
"""
import re
from collections import defaultdict
from urllib.parse import urlsplit

from config import DENOISE_MIN_LEADS_PER_DOMAIN, DENOISE_AGGREGATION_HIT_RATIO

# 功能性子域前缀，聚合时归并到主域（如 datasheets.globalspec.com → globalspec.com）
_FUNCTIONAL_SUBDOMAINS = frozenset(
    {"www", "m", "en", "de", "fr", "datasheets", "api", "mobile"}
)


def host_of(url: str) -> str:
    try:
        netloc = urlsplit(url).netloc.lower().split(":")[0]
    except Exception:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def platform_key(url: str) -> str:
    """动态平台键：功能性子域归并到 registrable domain（如 datasheets.globalspec.com → globalspec.com）。"""
    domain = host_of(url)
    parts = domain.split(".")
    if len(parts) >= 3 and parts[0] in _FUNCTIONAL_SUBDOMAINS:
        return ".".join(parts[1:])
    if len(parts) >= 3 and parts[0] == "datasheets":
        return ".".join(parts[1:])
    # europages.fr / europages.com → europages
    if len(parts) >= 2 and parts[0] == "europages":
        return "europages"
    return domain


def company_tokens(company: str, anchor: dict) -> list[str]:
    """从公司名与 anchor 生成用于匹配的 token（小写）。"""
    tokens: set[str] = set()
    for raw in [company, anchor.get("name", ""), *anchor.get("aliases", [])]:
        t = raw.strip().lower()
        if len(t) >= 2:
            tokens.add(t)
            tokens.add(re.sub(r"[^a-z0-9]", "", t))
            tokens.add(re.sub(r"[^a-z0-9]+", " ", t).strip())
    domain = (anchor.get("official_domain") or "").lower().strip()
    if domain:
        tokens.add(domain)
        stem = domain.split(".")[0]
        if len(stem) >= 2:
            tokens.add(stem)
    return [t for t in tokens if t]


def _text_blob(lead: dict) -> str:
    return " ".join([lead.get("url", ""), lead.get("title", ""), lead.get("snippet", "")]).lower()


def _min_token_len(token: str) -> int:
    """中文公司名常 2~4 字；英文 token 至少 3 字符避免误匹配。"""
    if re.search(r"[\u4e00-\u9fff]", token):
        return 2
    return 3


def _official_domain(anchor: dict) -> str:
    return (anchor.get("official_domain") or "").lower().strip()


def _on_official_domain(url: str, anchor: dict) -> bool:
    official = _official_domain(anchor)
    if not official:
        return False
    domain = host_of(url)
    return domain == official or domain.endswith(f".{official}")


def is_relevant_to_company(lead: dict, tokens: list[str], anchor: dict | None = None) -> bool:
    """线索内容是否与公司 token 相关。"""
    if anchor and _on_official_domain(lead.get("url", ""), anchor):
        return True
    if not tokens:
        return True
    blob = _text_blob(lead)
    domain = host_of(lead.get("url", ""))
    for t in tokens:
        if "." in t and t in domain:
            return True
    for t in tokens:
        if len(t) >= _min_token_len(t) and t in blob:
            return True
    return False


def domains_needing_denoise(inventory: list[dict], tokens: list[str], anchor: dict | None = None) -> set[str]:
    """
    动态识别需要去噪的域名（聚合站 / 名录站行为）：
    - 任一条线索被标为 marketplace_directory
    - 或：同域线索数 >= 阈值，且命中公司 token 的比例低于配置比例
    """
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for lead in inventory:
        by_domain[host_of(lead["url"])].append(lead)

    need: set[str] = set()
    for domain, leads in by_domain.items():
        if any((l.get("source_type") or "") == "marketplace_directory" for l in leads):
            need.add(domain)
            continue
        if len(leads) < DENOISE_MIN_LEADS_PER_DOMAIN:
            continue
        hits = sum(1 for l in leads if is_relevant_to_company(l, tokens, anchor))
        if hits / len(leads) < DENOISE_AGGREGATION_HIT_RATIO:
            need.add(domain)
    return need


def domain_is_marketplace(merged: dict, domain: str) -> bool:
    """BFS 扩展用：动态判断域名是否以名录/聚合为主。"""
    leads = [e for e in merged.values() if host_of(e.get("url", "")) == domain]
    if not leads:
        return False
    mp = sum(1 for e in leads if (e.get("source_type") or "") == "marketplace_directory")
    if mp > 0:
        return True
    # 同域多条且路径分散 → 聚合站特征
    if len(leads) >= DENOISE_MIN_LEADS_PER_DOMAIN:
        paths = {urlsplit(e.get("url", "")).path for e in leads}
        if len(paths) >= DENOISE_MIN_LEADS_PER_DOMAIN:
            return True
    return mp >= len(leads) / 2


def filter_directory_noise(
    inventory: list[dict],
    company: str,
    anchor: dict,
) -> tuple[list[dict], int]:
    """
    动态去噪：仅对「需要检查的域名/类型」上的线索做 token 过滤。
    返回 (过滤后清单, 剔除条数)。
    """
    tokens = company_tokens(company, anchor)
    noisy_domains = domains_needing_denoise(inventory, tokens, anchor)

    kept, removed = [], 0
    for lead in inventory:
        domain = host_of(lead["url"])
        st = lead.get("source_type") or ""
        needs_check = st == "marketplace_directory" or domain in noisy_domains
        if needs_check and not is_relevant_to_company(lead, tokens, anchor):
            removed += 1
            continue
        kept.append(lead)
    return kept, removed
