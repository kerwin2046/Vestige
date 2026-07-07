.PHONY: help up down run status logs \
	docker-up docker-up-crawler docker-camofox docker-down docker-check docker-logs

# 一键启动 Docker + 健康检查
up: docker-up-crawler status

down: docker-down

# 跑 Vestige pipeline（需在项目根目录、venv 已激活）
run:
	python3 main.py

status: docker-check

logs: docker-logs

help:
	@echo "Vestige 常用命令:"
	@echo "  make up      启动 SearXNG + Camofox，并做健康检查"
	@echo "  make run     运行足迹发现 pipeline"
	@echo "  make down    停止 Docker 栈"
	@echo "  make status  检查 SearXNG / Camofox / Cloak"
	@echo "  make logs    查看 Docker 日志"
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
