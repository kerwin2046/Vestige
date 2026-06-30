# config.py
from dotenv import load_dotenv

# 启动时自动加载密钥
load_dotenv()

# ==========================================
# ⚙️ 模型配置 (Model Identifier)
# ==========================================
# 如果直接调用服务商的原生模型
ACTIVE_MODEL = "deepseek/deepseek-v4-pro"       # 或者是 "openai/gpt-4o", "anthropic/claude-3-5-sonnet"

# 如果你使用的是中转平台（如 OpenRouter）
# ACTIVE_MODEL = "openrouter/deepseek/deepseek-chat"

SEARXNG_BASE_URL = "http://localhost:8080/search"

# ==========================================
# 🔌 检索后端 (Pluggable Search Backend)
# ==========================================
# 可选: "searxng"(本地免费,易被上游限流) / "ddg"(DuckDuckGo) / "brave"(带 key,稳定)
# brave 需要在 .env 配置 BRAVE_API_KEY
SEARCH_BACKEND = "ddg"

# 限流：避免“单 IP 高频”触发上游引擎的限流/CAPTCHA
SEARCH_MAX_CONCURRENCY = 3      # 同时最多并发几条查询
SEARCH_MIN_INTERVAL_SEC = 1.0   # 相邻两条查询的最小间隔(秒)

# ==========================================
# 🔎 公司足迹检索配置 (Step A: Query Fan-out)
# ==========================================
# 每条查询从 SearXNG 取多少条结果
MAX_RESULTS_PER_QUERY = 10

# 足迹清单(广度)不设上限：所有通过置信度的来源都会进入最终报告。
# 下面两个参数只控制“深度抓取+逐页抽取”这个昂贵子集的预算，不影响清单完整性。
MAX_URLS_TO_CRAWL = 15        # 最多深度抓取多少个页面(成本预算)
MAX_CRAWL_PER_DOMAIN = 2      # 同一域名最多抓几个页面(让预算铺开到更多来源，避免堆在一个站)

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
    # trade_show(展会)
    '"{company}" exhibition OR "trade show" OR booth',
    # association(协会/商会)
    '"{company}" association OR member',
    # marketplace_directory(B2B/供应商目录)
    '"{company}" supplier OR distributor OR B2B',
    # public_record(注册/专利)
    '"{company}" patent OR registration',
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
# 整个流程累计最多扩展多少个域名（全局预算，最硬的刹车）
MAX_TOTAL_DOMAINS_TO_EXPAND = 12

# 第二阶段域名扩展时跳过的“噪声/聚合”域名（搜索/社交大站按需保留或剔除）
DOMAIN_EXPANSION_BLOCKLIST = {
    "google.com", "bing.com", "duckduckgo.com", "youtube.com",
    "translate.google.com", "webcache.googleusercontent.com",
}

# ==========================================
# 🎯 Step B: 身份锚定与消歧 (Disambiguation)
# ==========================================
# 目标公司的“身份特征”。用来判断每条线索是不是同一家公司，
# 解决同名歧义（如 "Protolabs" 既是工业公司，也有同名 App/游戏/无关个人）。
# official_domain / industry / location / aliases 都可留空，但填得越多越准。
COMPANY_ANCHOR = {
    "name": "Protolabs",
    "official_domain": "protolabs.com",
    "industry": "工业制造 / 汽车零部件 / 快速成型",
    "location": "",
    "aliases": [],
}

# 线索的“同一家公司”置信度阈值（0~1）：
# - 低于该值的线索在最终结果里会被沉底/过滤
# - 低于该值的域名不会进入 BFS 扩展队列（避免越挖越偏）
RELEVANCE_THRESHOLD = 0.5

# ==========================================
# 💾 输出
# ==========================================
# 结构化结果(JSON)的落盘目录
OUTPUT_DIR = "output"
