#!/usr/bin/env bash
# Vestige Docker 健康检查
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEARXNG_URL="${SEARXNG_BASE_URL:-http://127.0.0.1:8080/search}"
CAMOFOX_URL="${CAMOFOX_BASE_URL:-http://127.0.0.1:9377}"

ok() { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; }

echo "Vestige Docker check"
echo

# --- SearXNG ---
if curl -sf --max-time 5 "${SEARXNG_URL}?q=health&format=json" >/dev/null 2>&1; then
  ok "SearXNG  ${SEARXNG_URL}"
else
  warn "SearXNG  未响应 — 运行: cd docker && docker compose up -d"
fi

# --- Camofox ---
if curl -sf --max-time 5 "${CAMOFOX_URL}/health" >/dev/null 2>&1; then
  ok "Camofox   ${CAMOFOX_URL}"
else
  warn "Camofox   未响应 — 运行: cd docker && docker compose --profile crawler up -d"
fi

# --- Cloak (npm, 非 Docker) ---
CLOAK_DIR="${ROOT}/scripts/cloak"
if [[ -d "${CLOAK_DIR}/node_modules" ]]; then
  ok "Cloak     scripts/cloak (npm 已安装)"
else
  warn "Cloak     未安装 — 运行: cd scripts/cloak && npm install"
fi

echo
if docker compose version >/dev/null 2>&1; then
  echo "Containers:"
  docker ps --filter "name=searxng" --filter "name=vestige-camofox" --format "  {{.Names}}\t{{.Status}}" 2>/dev/null || true
fi
