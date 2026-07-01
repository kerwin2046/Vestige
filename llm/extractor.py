# llm/extractor.py
"""
Step B: 身份锚定 + 消歧 + 逐页结构化抽取。

- score_leads():  抓取前，基于搜索结果(title/snippet)判断每条线索是不是同一家公司，
                  输出置信度。用于排序、过滤以及 BFS 扩展门控。
- extract_page(): 抓取后，对单个页面按固定 schema 结构化抽取。
"""
import json
import re

import litellm
from litellm import acompletion

# litellm 默认用 aiohttp 传输，进程退出时常抛 "Event loop is closed" 的 SSL 清理噪声。
# 改用 httpx 传输可干净关闭连接。
litellm.disable_aiohttp_transport = True

# ============================================================
# 双维度分类(参考 OSINT)：
#   维度1 source_type —— 内容来源的“性质/产生方式”(主分类)
#   维度2 ownership    —— 内容的“所有权关系”(第一方/第三方)
# 两者都是英文枚举(稳定机器键)，展示时再映射成中文。
# ============================================================
SOURCE_TYPES = [
    # "owned",                  # 自有/官方发布物(官网、官方博客、官方账号)
    "social",                 # 社媒/SOCMINT
    "community",              # 社区/论坛/Q&A/评论
    "news_media",             # 新闻媒体/编辑内容
    "community_ugc",          # 用户生成内容(论坛/评论/Q&A/对比帖)
    "marketplace_directory",  # 交易/名录(B2B平台、电商、企业黄页、供应商目录)
    # "reference",              # 参考/数据库(维基、企业信息库、行业百科)
    "public_record",          # 公开记录/监管(工商注册、专利、法律、招投标)
    # "recruitment",            # 招聘
    "academic_technical",     # 学术/技术(论文、技术文档、标准、白皮书)
    "event",                  # 展会/会议
    "other",                  # 其他
    "irrelevant",             # 同名无关
]

SOURCE_TYPE_LABELS = {
    # "owned": "自有/官方发布物",
    "social": "社媒/SOCMINT",
    "community": "社区/论坛/Q&A/评论",
    "news_media": "新闻媒体/编辑内容",
    "community_ugc": "用户生成内容(论坛/评论/Q&A/对比帖)",
    "marketplace_directory": "交易/名录(B2B平台、电商、企业黄页、供应商目录)",
    # "reference": "参考/数据库(维基、企业信息库、行业百科)",
    "public_record": "公开记录/监管(工商注册、专利、法律、招投标)",
    # "recruitment": "招聘",
    "academic_technical": "学术/技术(论文、技术文档、标准、白皮书)",
    "event": "展会/会议",
    "other": "其他",
    "irrelevant": "同名无关",
}

OWNERSHIP_TYPES = ["first_party", "third_party", "unknown"]

OWNERSHIP_LABELS = {
    "first_party": "第一方(公司自有)",
    "third_party": "第三方(他人提及)",
    "unknown": "未知",
}


def _normalize_enum(value: str, allowed: list[str], default: str) -> str:
    """把模型返回的枚举值归一化到允许集合，非法值回落到 default。"""
    if isinstance(value, str) and value.strip() in allowed:
        return value.strip()
    return default


def _anchor_text(anchor: dict) -> str:
    parts = [f"公司名: {anchor.get('name', '')}"]
    if anchor.get("official_domain"):
        parts.append(f"官网域名: {anchor['official_domain']}")
    if anchor.get("industry"):
        parts.append(f"行业: {anchor['industry']}")
    if anchor.get("location"):
        parts.append(f"地区: {anchor['location']}")
    if anchor.get("aliases"):
        parts.append(f"别名: {', '.join(anchor['aliases'])}")
    return "\n".join(parts)


def _parse_json(text: str):
    """从 LLM 返回里稳健地解析 JSON（容忍 ```json 包裹和前后噪声）。"""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # 退化：截取第一个 [..] 或 {..}
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = cleaned.find(open_ch)
        end = cleaned.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except Exception:
                continue
    return None


_SCORE_PROMPT = """你是公司情报分析师。下面是目标公司的“身份锚点”，以及一批从搜索引擎得到的线索（标题+摘要）。
请判断每一条线索“是否指向这同一家目标公司”，给出 0~1 的置信度，并按两个维度分类。

【目标公司身份锚点】
{anchor}

【判定要点】
- 官网域名命中、行业/地区吻合 → 高置信度
- 仅名字相同但明显是别的实体（同名 App、游戏、无关个人、纯聚合蹭词）→ 低置信度
- 信息不足无法判断 → 0.5 左右

【两个分类维度】
- source_type(内容来源性质)，从这里选: {source_types}
- ownership(所有权): {ownership_types}
  · first_party = 公司自己掌控的内容(官网、官方社媒账号)
  · third_party = 别人提到它(媒体、论坛、目录、他人主页)
  · unknown = 无法判断

【线索列表】(JSON)
{leads}

请严格只输出 JSON 数组，每个元素形如：
{{"index": 0, "confidence": 0.0~1.0, "source_type": "...", "ownership": "...", "reason": "简短理由"}}
不要输出除 JSON 以外的任何文字。"""


async def score_leads(company: str, anchor: dict, leads: list[dict], model: str) -> dict[str, dict]:
    """
    对一批线索做消歧打分。

    leads: [{"url":..., "title":..., "snippet":...}, ...]
    返回: {url: {"confidence": float, "source_type": str, "ownership": str, "reason": str}}
    解析失败时返回空 dict（调用方应作降级处理）。
    """
    if not leads:
        return {}

    compact = [
        {"index": i, "url": d.get("url", ""), "title": d.get("title", ""), "snippet": d.get("snippet", "")}
        for i, d in enumerate(leads)
    ]
    prompt = _SCORE_PROMPT.format(
        anchor=_anchor_text(anchor),
        leads=json.dumps(compact, ensure_ascii=False),
        source_types="/".join(SOURCE_TYPES),
        ownership_types="/".join(OWNERSHIP_TYPES),
    )

    try:
        resp = await acompletion(model=model, messages=[{"role": "user", "content": prompt}])
        parsed = _parse_json(resp.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ 消歧打分失败: {e}")
        return {}

    if not isinstance(parsed, list):
        return {}

    out: dict[str, dict] = {}
    for item in parsed:
        try:
            idx = int(item["index"])
            url = leads[idx].get("url", "")
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if not url:
            continue
        try:
            conf = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        out[url] = {
            "confidence": max(0.0, min(1.0, conf)),
            "source_type": _normalize_enum(item.get("source_type"), SOURCE_TYPES, "other"),
            "ownership": _normalize_enum(item.get("ownership"), OWNERSHIP_TYPES, "unknown"),
            "reason": item.get("reason", ""),
        }
    return out


_EXTRACT_PROMPT = """你是公司情报分析师。下面是目标公司的身份锚点，以及抓取到的某个网页内容。
请只依据网页内容，抽取与“目标公司全网足迹”相关的结构化信息。

【目标公司身份锚点】
{anchor}

【网页 URL】
{url}

【网页内容】
{content}

【两个分类维度】
- source_type(内容来源性质)，从这里选: {source_types}
- ownership(所有权): {ownership_types}
  · first_party = 公司自己掌控(官网、官方账号)；third_party = 他人提及；unknown = 无法判断

请严格只输出一个 JSON 对象：
{{
  "source_type": "...",
  "ownership": "...",
  "company_name_on_page": "页面里出现的公司/实体名称",
  "profile_or_handle": "该来源上的账号/主页/店铺标识，没有则空字符串",
  "contacts": {{"email": "", "phone": ""}},
  "evidence_snippet": "能证明与目标公司相关的关键原文片段(<=200字)",
  "is_same_company_confidence": 0.0~1.0
}}
不要输出除 JSON 以外的任何文字。"""


async def extract_page(company: str, anchor: dict, url: str, content: str, model: str) -> dict:
    """对单个页面做结构化抽取，返回 schema dict（带 source_url）。失败返回低置信度占位。"""
    fallback = {
        "source_url": url,
        "source_type": "other",
        "ownership": "unknown",
        "company_name_on_page": "",
        "profile_or_handle": "",
        "contacts": {"email": "", "phone": ""},
        "evidence_snippet": "",
        "is_same_company_confidence": 0.0,
    }
    if not content or not content.strip():
        return fallback

    prompt = _EXTRACT_PROMPT.format(
        anchor=_anchor_text(anchor),
        url=url,
        content=content,
        source_types="/".join(SOURCE_TYPES),
        ownership_types="/".join(OWNERSHIP_TYPES),
    )
    try:
        resp = await acompletion(model=model, messages=[{"role": "user", "content": prompt}])
        parsed = _parse_json(resp.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ 页面抽取失败 {url}: {e}")
        return fallback

    if not isinstance(parsed, dict):
        return fallback

    parsed.setdefault("contacts", {"email": "", "phone": ""})
    parsed["source_type"] = _normalize_enum(parsed.get("source_type"), SOURCE_TYPES, "other")
    parsed["ownership"] = _normalize_enum(parsed.get("ownership"), OWNERSHIP_TYPES, "unknown")
    try:
        parsed["is_same_company_confidence"] = max(
            0.0, min(1.0, float(parsed.get("is_same_company_confidence", 0.0)))
        )
    except (TypeError, ValueError):
        parsed["is_same_company_confidence"] = 0.0
    parsed["source_url"] = url
    return parsed
