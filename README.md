# Vestige

> 追踪一家公司在全网留下的所有踪迹。
>
> Vestige 是一个公司网络足迹情报工具(Company Web Footprint Intelligence):给定一个公司名,自动发现它在全网出现的所有地方——官网、社媒、展会、协会、B2B 平台、新闻、论坛、招聘、公开记录等——并按"来源类型 × 所有权"结构化归类。

---

## 它做什么

输入一个公司名(及可选的身份特征),Vestige 会:

1. **多轮 BFS 来源发现**:用少量高覆盖查询广度发现"哪些来源在提这家公司",再针对发现的域名动态深挖,一轮轮顺藤摸瓜(受深度/预算刹车控制)。
2. **身份消歧**:基于身份锚点(官网域名/行业/地区)判断每条线索"是不是同一家公司",过滤同名 App、游戏、无关个人等噪声。
3. **结构化抽取**:对多样化子集抓取网页,用 LLM 按固定 schema 抽取(来源类型、所有权、联系方式、证据片段)。
4. **输出**:一份完整的足迹清单(控制台报告 + Excel 文件)。

## 架构 / 流水线

![Vestige 架构](Vestige.png)

## 双维度分类(参考 OSINT)

每个来源按两个正交维度标注:

- **source_type(内容来源性质)**:`owned / social / news_media / community_ugc / marketplace_directory / reference / public_record / recruitment / academic_technical / other / irrelevant`
- **ownership(所有权)**:`first_party`(公司自有) / `third_party`(他人提及) / `unknown`

内部用英文枚举(稳定机器键),报告展示时映射成中文。

## 项目结构

```
.
├── main.py                 # 入口
├── pipeline.py             # 编排 + 报告渲染 + Excel 落盘
├── config.py               # 所有配置(模型/后端/检索/BFS/锚点)
├── search/
│   ├── backends.py         # 可插拔检索后端 + 限流器
│   └── search_engine.py    # 多轮 BFS、去重打分、消歧门控
├── crawlers/
│   └── scraper.py          # Crawl4AI 抓取
├── llm/
│   └── extractor.py        # 消歧打分 + 逐页结构化抽取
├── searxng/                # 自建 SearXNG 的 docker-compose
├── requirements.txt
└── output/                 # 结构化结果 Excel(运行后生成, .gitignore)
```

## 安装

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Crawl4AI 首次使用需要装浏览器内核
crawl4ai-setup
```

## 配置

### 1. 环境变量 `.env`

按所选模型/后端配置对应的 key,例如:

```bash
# LLM(litellm 透传，按你的服务商填)
DEEPSEEK_API_KEY=sk-xxx
# 若用 Brave 检索后端
BRAVE_API_KEY=xxx
```

### 2. `config.py` 关键项

| 配置 | 说明 |
|---|---|
| `ACTIVE_MODEL` | litellm 模型名,如 `deepseek/deepseek-chat`、`openai/gpt-4o` |
| `SEARCH_BACKEND` | `exa` / `ddg` / `searxng` / `brave`,一行切换检索源 |
| `SEARCH_MAX_CONCURRENCY` / `SEARCH_MIN_INTERVAL_SEC` | 检索限流(避免被上游反爬) |
| `COMPANY_ANCHOR` | 目标公司身份锚点(名称/官网/行业/地区/别名),消歧的基准 |
| `RELEVANCE_THRESHOLD` | 置信度阈值,低于则过滤、且不进 BFS 扩展 |
| `SCORE_LEADS_BATCH_SIZE` | LLM 消歧每批线索数(过大易触发上游 500) |
| `SCORE_LEADS_MAX_RETRIES` / `SCORE_LEADS_RETRY_BACKOFF_SEC` | 消歧 5xx/超时重试 |
| `SCORE_LEADS_BFS_ABORT_UNSCORED_RATIO` | 未评分线索占比超此值则停止 BFS |
| `MAX_BFS_ROUNDS` / `MAX_DOMAINS_PER_ROUND` / `MAX_TOTAL_DOMAINS_TO_EXPAND` | BFS 三道刹车 |
| `MAX_URLS_TO_CRAWL` / `MAX_CRAWL_PER_DOMAIN` | 深度抓取的成本预算(不影响足迹清单完整性) |
| `DISCOVERY_QUERY_TEMPLATES` / `FOCUSED_QUERY_TEMPLATES` | 广度/深挖查询模板 |

### 3.(可选)自建 SearXNG

```bash
cd searxng
docker compose up -d   # 默认 http://localhost:8080
```

## 使用

编辑 `config.py` 里的 `COMPANY_ANCHOR` 填入目标公司,然后:

```bash
python3 main.py
```

控制台会打印分组后的足迹报告,同时在 `output/<公司名>.xlsx` 写入结构化结果。

## 输出

### 控制台报告

```
# 公司「Protolabs」全网足迹清单
共发现 N 个可信来源，其中 M 个做了深度抽取。按来源类型(source_type)分组：

## 自有/官方 (4)
- [100% · 第一方(公司自有)] https://www.protolabs.com/
    联系方式: contact@protolabs.com
    证据: ...
## 社媒 (1)
- [100% · 第一方(公司自有)] https://www.linkedin.com/company/proto-labs/
...
```

### Excel (`output/<公司名>.xlsx`)

三个工作表:

| 工作表 | 内容 |
|--------|------|
| **摘要** | 公司信息、生成时间、来源类型/归属统计 |
| **足迹清单** | 全部可信来源(URL 可点击)，含深度抽取的联系方式与证据 |
| **平台聚合** | 名录/B2B 类来源按平台汇总 |

> **足迹清单**包含全部通过置信度的来源;未做深度抽取的行，深度相关列为空。

## 检索后端说明

| 后端 | 特点 | 适用 |
|---|---|---|
| `exa` | Exa 神经搜索 API,稳定、支持 `include_domains` | **推荐**,替代 DDG/SearXNG |
| `ddg` | DuckDuckGo(`ddgs` 库),免费免 key | 原型/备用 |
| `searxng` | 自建元搜索,聚合多引擎 | 易 CAPTCHA,不推荐高频 BFS |
| `brave` | Brave Search API,稳定 | 上量 / 生产 |

**限流提醒**:`ddg` 与 `searxng` 易被 CAPTCHA;推荐 `exa`(`.env` 配 `EXA_API_KEY`)或 `brave`。
`site:` 查询在 Exa 后端会自动转为 `include_domains`。

## 注意事项

- 这是一个研究/自用性质的情报聚合工具,请遵守各平台 ToS 与当地数据合规要求。
- LinkedIn/Facebook 等平台对爬虫敏感,直接抓取常拿不到完整内容,通常只能依赖搜索摘要。
- LLM 消歧失败时线索保持 `confidence=None`,不会默认 0.5 放行 BFS;请检查 `ACTIVE_MODEL` 与 API 可用性,或调小 `SCORE_LEADS_BATCH_SIZE`。

## 技术栈

Python · asyncio · [Crawl4AI](https://github.com/unclecode/crawl4ai) · [LiteLLM](https://github.com/BerriAI/litellm) · [ddgs](https://github.com/deedy5/duckduckgo_search) · [SearXNG](https://github.com/searxng/searxng) · httpx
