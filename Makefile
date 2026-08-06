.PHONY: help up down run api web worker import-output import-intel import-b2b import-competitors sync-companies sync-expomind scaffold-agents run-agent backfill-signals dispatch-signals dispatch-stream migrate-mfg-stream status logs \
	docker-up docker-up-crawler docker-camofox docker-down docker-check docker-logs

# 全部 Python 代码在 backend/；以前端 frontend/ 对称。
export PYTHONPATH := $(CURDIR)/backend

# 优先用项目 venv 的解释器；没有 venv 时回退到系统 python3。
# 避免 worker/CLI 误用系统 python 导致 crawl4ai/exa_py 等依赖缺失而“静默半死”。
PY := $(if $(wildcard $(CURDIR)/venv/bin/python),$(CURDIR)/venv/bin/python,python3)

# 一键启动 Docker + 健康检查
up: docker-up-crawler status

down: docker-down

# 跑 Vestige pipeline（需在项目根目录、venv 已激活）
run:
	$(PY) backend/main.py

# 启动 Web Admin 后端 API（FastAPI，端口 8001；避开本机常见 :8000 占用）
api:
	$(PY) -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload --app-dir backend

# 启动 Web Admin 前端（Vite，端口 9091，代理到 :8001）
web:
	cd frontend && pnpm dev

# 启动发现任务 worker（轮询 queued runs）
worker:
	$(PY) -m worker

# 把 output/*.xlsx 与 output/*.json 历史结果导入 SQLite（幂等，可重复跑）
import-output:
	$(PY) -m scripts.import_output

# Vestige ↔ MfgRadar 公司主数据双向同步（按域名对齐）
sync-companies:
	$(PY) -m scripts.sync_company_master

# ExpoMind 精选同步：竞品→Targets，Yes/High 潜客→Candidates
sync-expomind:
	$(PY) -m scripts.sync_expomind

# 导入 competitive-intel/intel.db 信号到 Vestige（按竞品落成 run + sources）
import-intel:
	$(PY) -m scripts.import_intel_db

# 导入 B2B Platform Radar 平台/协会到 Vestige channels
import-b2b:
	$(PY) -m scripts.import_b2b_db

# 导入同行 Excel（竞品 Targets）：同行列表 + 中国同行背调
import-competitors:
	$(PY) -m scripts.import_competitor_xlsx

# 为已有公司批量生成 OpenClaw agent 目录
scaffold-agents:
	$(PY) -m scripts.scaffold_agents

# 从历史 signal / competitive-intel runs 回填 company_signals 实体表
backfill-signals:
	$(PY) -m scripts.backfill_company_signals

# 共享 signals-collector：按队列批量派发（默认 monitoring + 超 20h 未采）
# 用法: make dispatch-signals
#       make dispatch-signals LIMIT=10 TIER=target
#       make dispatch-signals LIMIT=5 WAIT=1 LOCAL=1
#       make dispatch-signals SCAFFOLD_ONLY=1
dispatch-signals:
	$(PY) -m scripts.dispatch_signals \
		$(if $(SCAFFOLD_ONLY),--scaffold-only) \
		$(if $(LIMIT),--limit $(LIMIT)) \
		$(if $(TIER),--tier "$(TIER)") \
		$(if $(ROLE),--role "$(ROLE)") \
		$(if $(ALL_FRESH),--all-fresh) \
		$(if $(WAIT),--wait) \
		$(if $(LOCAL),--local) \
		$(if $(TIMEOUT),--timeout $(TIMEOUT))

# 种子 mfg-social stream，并把「通用」信号迁到 stream + 目录隐藏
migrate-mfg-stream:
	$(PY) -m scripts.migrate_generic_to_stream $(if $(DRY_RUN),--dry-run)

# 制造业社媒热度 stream agent（独立于公司 collector）
# 用法: make dispatch-stream
#       make dispatch-stream WAIT=1 LOCAL=1
#       make dispatch-stream SCAFFOLD_ONLY=1
dispatch-stream:
	$(PY) -m scripts.dispatch_stream \
		$(if $(SCAFFOLD_ONLY),--scaffold-only) \
		$(if $(WAIT),--wait) \
		$(if $(LOCAL),--local) \
		$(if $(TIMEOUT),--timeout $(TIMEOUT)) \
		$(if $(THINKING),--thinking "$(THINKING)")

# 通过 OpenClaw CLI 跑某公司 agent（需 gateway；无 gateway 时 LOCAL=1）
# 用法: make run-agent DOMAIN=xometry.com
#       make run-agent ID=<uuid> DETACH=1
#       make run-agent DOMAIN=xometry.com LOCAL=1
run-agent:
	@if [ -z "$(DOMAIN)$(ID)$(SLUG)$(NAME)" ]; then \
		echo "Usage: make run-agent DOMAIN=xometry.com | ID=<uuid> | SLUG=xometry | NAME=Xometry"; \
		exit 1; \
	fi
	$(PY) -m scripts.run_openclaw_agent \
		$(if $(ID),--id "$(ID)") \
		$(if $(DOMAIN),--domain "$(DOMAIN)") \
		$(if $(SLUG),--slug "$(SLUG)") \
		$(if $(NAME),--name "$(NAME)") \
		$(if $(DETACH),--detach) \
		$(if $(LOCAL),--local) \
		$(if $(TIMEOUT),--timeout $(TIMEOUT)) \
		$(if $(THINKING),--thinking "$(THINKING)")

status: docker-check

logs: docker-logs

help:
	@echo "Vestige 常用命令:"
	@echo "  make up            启动 SearXNG + Camofox，并做健康检查"
	@echo "  make run           运行足迹发现 pipeline（CLI）"
	@echo "  make api           启动 Web Admin 后端 API（FastAPI :8001）"
	@echo "  make web           启动 Web Admin 前端（Vite :9091，代理到 :8001）"
	@echo "  make worker        启动发现任务 worker（消费 queued runs）"
	@echo "  make import-output   导入 output/ 历史 Excel/JSON 到 SQLite"
	@echo "  make import-intel      导入 competitive-intel/intel.db 到 Vestige"
	@echo "  make import-b2b        导入 B2B Radar 平台/协会到 Channels"
	@echo "  make import-competitors 导入同行 Excel 为竞品 Targets"
	@echo "  make sync-companies    同步 Vestige ↔ MfgRadar 公司主数据"
	@echo "  make sync-expomind     同步 ExpoMind 竞品/高优潜客（分层）"
	@echo "  make scaffold-agents   为已有公司生成 OpenClaw agent 目录"
	@echo "  make backfill-signals  回填 company_signals（历史 signal runs）"
	@echo "  make dispatch-signals  共享 collector 按队列派发 signals"
	@echo "  make migrate-mfg-stream 种子 mfg-social 并迁移「通用」"
	@echo "  make dispatch-stream   制造业社媒热度 stream agent"
	@echo "  make run-agent DOMAIN=…  调用 OpenClaw 跑该公司 agent（默认共享 collector）"
	@echo "  make down            停止 Docker 栈"
	@echo "  make status        检查 SearXNG / Camofox / Cloak"
	@echo "  make logs          查看 Docker 日志"
	@echo ""
	@echo "细分:"
	@echo "  make docker-up          仅 SearXNG"
	@echo "  make docker-camofox     仅 Camofox（SearXNG 已在跑时）"

docker-up:
	cd docker && docker compose --env-file ../.env up -d

# SearXNG + Camofox（推荐）
docker-up-crawler:
	cd docker && docker compose --env-file ../.env --profile crawler up -d

# 仅 Camofox（SearXNG 已在 searxng/ 运行时）
docker-camofox:
	cd docker && docker compose --env-file ../.env --profile crawler up -d camofox

docker-down:
	cd docker && docker compose --profile crawler down

docker-check:
	bash docker/check.sh

docker-logs:
	cd docker && docker compose --profile crawler logs -f --tail=100
