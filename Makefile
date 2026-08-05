.PHONY: help up down run api web worker import-output import-intel import-b2b sync-companies sync-expomind scaffold-agents status logs \
	docker-up docker-up-crawler docker-camofox docker-down docker-check docker-logs

# 全部 Python 代码在 backend/；以前端 frontend/ 对称。
export PYTHONPATH := $(CURDIR)/backend

# 一键启动 Docker + 健康检查
up: docker-up-crawler status

down: docker-down

# 跑 Vestige pipeline（需在项目根目录、venv 已激活）
run:
	python3 backend/main.py

# 启动 Web Admin 后端 API（FastAPI，端口 8001；避开本机常见 :8000 占用）
api:
	python3 -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload --app-dir backend

# 启动 Web Admin 前端（Vite，端口 9091，代理到 :8001）
web:
	cd frontend && pnpm dev

# 启动发现任务 worker（轮询 queued runs）
worker:
	python3 -m worker

# 把 output/*.xlsx 与 output/*.json 历史结果导入 SQLite（幂等，可重复跑）
import-output:
	python3 -m scripts.import_output

# Vestige ↔ MfgRadar 公司主数据双向同步（按域名对齐）
sync-companies:
	python3 -m scripts.sync_company_master

# ExpoMind 精选同步：竞品→Targets，Yes/High 潜客→Candidates
sync-expomind:
	python3 -m scripts.sync_expomind

# 导入 competitive-intel/intel.db 信号到 Vestige（按竞品落成 run + sources）
import-intel:
	python3 -m scripts.import_intel_db

# 导入 B2B Platform Radar 平台/协会到 Vestige channels
import-b2b:
	python3 -m scripts.import_b2b_db

# 为已有公司批量生成 OpenClaw agent 目录
scaffold-agents:
	python3 -m scripts.scaffold_agents

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
	@echo "  make sync-companies    同步 Vestige ↔ MfgRadar 公司主数据"
	@echo "  make sync-expomind     同步 ExpoMind 竞品/高优潜客（分层）"
	@echo "  make scaffold-agents   为已有公司生成 OpenClaw agent 目录"
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
