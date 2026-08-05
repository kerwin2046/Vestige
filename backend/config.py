# config.py
import os
from pathlib import Path

from dotenv import load_dotenv

# 启动时自动加载密钥（仓库根目录 .env）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()  # 也允许从当前工作目录覆盖
# ==========================================
# ⚙️ 模型配置 (Model Identifier)
# ==========================================
# Agnes API (OpenAI 兼容): 在 .env 配置 OPENAI_API_KEY + OPENAI_API_BASE
ACTIVE_MODEL = "deepseek/deepseek-v4-flash"

SEARXNG_BASE_URL = "http://localhost:8080/search"
# SearXNG 单次查询只用哪些引擎(逗号分隔)。留空=实例默认引擎列表（推荐）。
# engines= 是 VPS/已烧 IP 时的权衡（缩小到 brave,duckduckgo,wikipedia 等更耐限流的子集），
# 不是住宅 IP + 低并发场景的默认做法。
SEARXNG_ENGINES = ""
# API 请求语言：en / all 最稳；zh-CN 易导致上游解析错误与 CAPTCHA
SEARXNG_LANGUAGE = "en"
# SearXNG 客户端限流：每次查询会扇出到大量上游，高并发最容易触发 CAPTCHA。
# 建议 ≤2–3 并发、约 ≤10 次/分钟（住宅 IP）；VPS 更保守。
SEARXNG_MAX_CONCURRENCY = 2
SEARXNG_MIN_INTERVAL_SEC = 6.0

# ==========================================
# 🔌 检索后端 (Pluggable Search Backend)
# ==========================================
# 可选引擎见 search/web/registry.py KNOWN_ENGINES，例如:
# exa / exa-mcp / searxng / duckduckgo / brave / serper / bing / tavily / bocha
# google_pse / perplexity / kagi / jina / mojeek / serpapi
# 引擎实现在 search/web/，由 registry.search_web() 调度（Open WebUI 风格）
SEARCH_BACKEND = "exa"
# 主引擎失败或 0 结果时依次尝试（逗号分隔名称，留空=不降级）
# 示例: SEARCH_FALLBACK_BACKENDS = ["searxng"]
SEARCH_FALLBACK_BACKENDS = ["searxng"]

# Exa API — https://docs.exa.ai/reference/search-api-guide-for-coding-agents
# type: auto(默认) | fast | instant | deep-lite | deep | deep-reasoning
EXA_SEARCH_TYPE = "auto"
EXA_MAX_CONCURRENCY = 3
EXA_MIN_INTERVAL_SEC = 0.5

# Exa MCP (SEARCH_BACKEND=exa-mcp) — 通过 mcporter 调用 https://mcp.exa.ai/mcp
# 安装: npm install -g mcporter && mcporter config add exa https://mcp.exa.ai/mcp
MCPORTER_BIN = "mcporter"
EXA_MCP_TIMEOUT_SEC = 60.0

# 限流：避免“单 IP 高频”触发上游引擎的限流/CAPTCHA
# 非 SearXNG 引擎默认；SearXNG 见上方 SEARXNG_*（更严）
SEARCH_MAX_CONCURRENCY = 2      # 同时最多并发几条查询
SEARCH_MIN_INTERVAL_SEC = 2.0   # 相邻两条查询的最小间隔(秒)

# Bing Web Search API (SEARCH_BACKEND=bing)
BING_SEARCH_V7_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
BING_LOCALE = "zh-CN"  # site: 与中文公司名可改为 zh-CN；国际公司可用 en-US

# Google PSE (SEARCH_BACKEND=google_pse) — Custom Search JSON API
# GOOGLE_PSE_API_KEY + GOOGLE_PSE_ENGINE_ID in .env；可选 GOOGLE_PSE_REFERER

# Perplexity Search (SEARCH_BACKEND=perplexity) — PERPLEXITY_API_KEY in .env
# 可选 PERPLEXITY_SEARCH_API_URL（默认 https://api.perplexity.ai/search）

# Kagi / Jina / Mojeek — KAGI_SEARCH_API_KEY / JINA_API_KEY / MOJEEK_SEARCH_API_KEY
# Jina 可选 JINA_SEARCH_BASE_URL（默认 https://s.jina.ai/）

# SerpApi (SEARCH_BACKEND=serpapi) — SERPAPI_API_KEY in .env
# 可选 SERPAPI_ENGINE（默认 google；亦可在 config.SERPAPI_ENGINE 设置）
SERPAPI_ENGINE = "google"

# ==========================================
# 🔎 公司足迹检索配置 (Step A: Query Fan-out)
# ==========================================
# 每条查询从 SearXNG 取多少条结果
MAX_RESULTS_PER_QUERY = 10

# 足迹清单(广度)不设上限：所有通过置信度的来源都会进入最终报告。
# 下面两个参数只控制“深度抓取+逐页抽取”这个昂贵子集的预算，不影响清单完整性。
MAX_URLS_TO_CRAWL = 15        # 最多深度抓取多少个页面(成本预算)
MAX_CRAWL_PER_DOMAIN = 1      # 同一域名只抓 1 个页面(深抓目的是抽样验证，非穷举同站)

# ------------------------------------------
# 两阶段检索：Discovery(广度发现) -> Focused(针对来源深挖)
# ------------------------------------------
# Phase 1 — Discovery：少量高覆盖查询，目的是“发现有哪些网站/平台在提这家公司”，
# 而不是一次性堆很多模板。用 {company} 占位。
# 按来源维度(source_type)各留 1~2 条，覆盖更全而不偏科。discovery 只在 Round 0 跑一次。
# 注：filetype:/site: 等高级语法在 DDG 后端支持较弱，换 Brave/Bing 后端时更可靠。
DISCOVERY_QUERY_TEMPLATES = [
    # 泛 / owned(官网)
    '"{company}"',
    '"{company}" official website OR contact',
    # social(社媒)
    '"{company}" linkedin OR facebook OR youtube',
    # community / ugc(社区/评论/对比)
    '"{company}" review',
    '"{company}" forum OR reddit',
    '"{company}" vs',
    # news_media(新闻)
    '"{company}" news',
    # public_record(注册/专利)
    '"{company}" patent OR registration',
    # trade_show(展会) — 定向平台 + 参展语义
    '"{company}" exhibitor OR booth OR "trade show"',
    '"{company}" site:10times.com OR site:messe.de OR site:eventseye.com',
    # association(协会/商会) — 中英
    '"{company}" chamber of commerce OR trade association',
    '"{company}" 商会 OR 协会 OR 会员单位',
    # marketplace_directory(B2B/供应商目录) — 国内平台
    '"{company}" site:alibaba.com OR site:made-in-china.com',
    '"{company}" supplier OR distributor OR B2B',
    # 文档(catalog/whitepaper)
    '"{company}" filetype:pdf',
]

# Phase 2 — Focused：根据第一阶段发现的来源域名“动态”生成定向查询。
# {site} 为发现的域名(如 forum.makeitfrom.com)，{company} 为公司名。
# 精简：focused 是“每域名 × 每轮”乘法放大，保持少而精。
# 第 1 条捞该域名上所有相关页；第 2 条专挖公司在该来源的门面/联系方式。
FOCUSED_QUERY_TEMPLATES = [
    'site:{site} "{company}"',
    'site:{site} "{company}" contact OR about OR profile',
]

# ------------------------------------------
# 多轮 BFS 来源发现的“刹车”参数（防止无限扩张）
# ------------------------------------------
# 在 Discovery 之后，最多再进行多少轮 Focused 深挖（控制 BFS 深度）
MAX_BFS_ROUNDS = 3
# 每一轮最多扩展多少个新域名（按得分 best-first 选取）
MAX_DOMAINS_PER_ROUND = 5
# 每轮 BFS 扩展时，名录站域名最多占几个名额（其余留给展会/协会/社媒等）
MAX_MARKETPLACE_DOMAINS_PER_ROUND = 3
# 整个流程累计最多扩展多少个域名（全局预算，最硬的刹车）
MAX_TOTAL_DOMAINS_TO_EXPAND = 12

# 第二阶段域名扩展时跳过的「噪声/聚合」域名（搜索大站 + 联系人/对比黄页）
# 完整名单见下方 DOMAIN_EXPANSION_BLOCKLIST（与去噪配置同段）

# ==========================================
# 🎯 Step B: 身份锚定与消歧 (Disambiguation)
# ==========================================
# 目标公司的“身份特征”。用来判断每条线索是不是同一家公司，
# 解决同名歧义（如 "Protolabs" 既是工业公司，也有同名 App/游戏/无关个人）。
# official_domain / industry / location / aliases 都可留空，但填得越多越准。
COMPANY_ANCHOR = {
    "name": "hanslaser",
    "official_domain": "hanslaser.com",
    "industry": "3D Printing / Additive Manufacturing / Rapid Prototyping",
    "location": "",
    # 短中文名歧义大：尽量补全称、英文名、股票简称等，显著提升消歧通过率
    "aliases": ["hanslaser", "hanslaser Inc.", "hanslaser Inc"],
}

# 线索的“同一家公司”置信度阈值（0~1）：
# - 低于该值的线索在最终结果里会被沉底/过滤
# - 低于该值的域名不会进入 BFS 扩展队列（避免越挖越偏）
RELEVANCE_THRESHOLD = 0.5

# LLM 消歧打分（score_leads）：分批与重试，避免单次 prompt 过大触发上游 500
SCORE_LEADS_BATCH_SIZE = 20
SCORE_LEADS_MAX_RETRIES = 2
SCORE_LEADS_RETRY_BACKOFF_SEC = 2.0
SCORE_LEADS_SNIPPET_MAX = 300
# 消歧后未评分线索占比超过此值则停止 BFS（避免盲扩）
SCORE_LEADS_BFS_ABORT_UNSCORED_RATIO = 0.3

# ==========================================
# 🧹 名录站去噪（动态，无静态站名单）
# ==========================================
# 同一域名至少几条线索，才用「聚合站」行为启发式判定
DENOISE_MIN_LEADS_PER_DOMAIN = 3
# 该域名下命中公司 token 的线索比例低于此值 → 视为聚合站，做 token 去噪
DENOISE_AGGREGATION_HIT_RATIO = 0.5

# 同域名在最终清单里最多保留几条
MAX_URLS_PER_DOMAIN_IN_INVENTORY = 3
# 官网/公司自有站：只留 1 条代表链接（首页或 contact 优先）
MAX_URLS_PER_OFFICIAL_DOMAIN = 1
# 联系人黄页、软件对比站等聚合域名更严格
MAX_URLS_PER_AGGREGATOR_DOMAIN = 2
# BFS 不再向这些域名做 site: 深挖（Discovery 仍可能命中）
DOMAIN_EXPANSION_BLOCKLIST = {
    "google.com", "bing.com", "duckduckgo.com", "youtube.com",
    "translate.google.com", "webcache.googleusercontent.com",
    # 联系人/对比类聚合站：深挖只会刷出大量同质页
    "rocketreach.co", "zoominfo.com", "apollo.io", "lusha.com",
    "slashdot.org", "g2.com", "capterra.com", "softwareadvice.com",
}

# ==========================================
# 📥 页面抓取 (Crawler Registry)
# ==========================================
# 反爬升级链：crawl4ai → camofox → cloak（仅对上一轮失败的 URL 继续尝试）
CRAWLER_ESCALATION = True
CRAWLER_CHAIN = ["crawl4ai", "camofox", "cloak"]
MAX_CHARS_PER_PAGE = 6000

CAMOFOX_BASE_URL = os.getenv("CAMOFOX_BASE_URL", "http://127.0.0.1:9377")
CAMOFOX_USER_ID = os.getenv("CAMOFOX_USER_ID", "vestige")
CAMOFOX_API_KEY = os.getenv("CAMOFOX_API_KEY", "")
CAMOFOX_TIMEOUT_SEC = float(os.getenv("CAMOFOX_TIMEOUT_SEC", "45"))

# 留空则使用 scripts/cloak/cloak-fetch.mjs
CLOAK_SCRIPT = os.getenv(
    "CLOAK_SCRIPT",
    str(_PROJECT_ROOT / "scripts" / "cloak" / "cloak-fetch.mjs"),
)
CLOAK_TIMEOUT_SEC = float(os.getenv("CLOAK_TIMEOUT_SEC", "60"))

# ==========================================
# 💾 输出
# ==========================================
# 结构化结果(JSON)的落盘目录
OUTPUT_DIR = "output"
