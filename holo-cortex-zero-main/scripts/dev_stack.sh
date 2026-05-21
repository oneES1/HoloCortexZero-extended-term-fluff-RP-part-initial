#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.dev.yml"
FRONTEND_DIR="${REPO_ROOT}/frontend"
MODE="${1:-}"

log() {
  printf '[dev-stack] %s\n' "$*"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "缺少命令: ${cmd}"
    exit 1
  fi
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  local timeout="${4:-30}"
  local i
  for ((i=0; i<timeout; i++)); do
    if (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
      log "${label} 已就绪: ${host}:${port}"
      return 0
    fi
    sleep 1
  done
  log "等待超时: ${label} ${host}:${port}"
  return 1
}

show_help() {
  cat <<'EOF'
用法:
  bash scripts/dev_stack.sh [--docs]
EOF
}

cleanup() {
  local code=$?
  trap - EXIT INT TERM
  if [[ -n "${backend_pid:-}" ]] && kill -0 "${backend_pid}" >/dev/null 2>&1; then
    kill "${backend_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${frontend_pid:-}" ]] && kill -0 "${frontend_pid}" >/dev/null 2>&1; then
    kill "${frontend_pid}" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  if [[ ${code} -ne 0 ]]; then
    log "前后端开发进程已停止，开发依赖容器保持运行"
  fi
  exit ${code}
}

case "${MODE}" in
  ""|"--docs") ;;
  "-h"|"--help")
    show_help
    exit 0
    ;;
  *)
    log "未知参数: ${MODE}"
    show_help
    exit 1
    ;;
esac

require_cmd docker
require_cmd uv
require_cmd pnpm
require_cmd bash

if ! docker compose version >/dev/null 2>&1; then
  log 'docker compose 不可用'
  exit 1
fi

if ! uv python find 3.11 >/dev/null 2>&1; then
  log '未找到 Python 3.11；请先安装可供 uv 使用的 Python 3.11'
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  log '缺少 frontend/node_modules，请先执行: pnpm --dir frontend install --frozen-lockfile'
  exit 1
fi

log '启动开发依赖容器'
docker compose -f "${COMPOSE_FILE}" up -d
wait_for_port 127.0.0.1 5433 'Postgres'
wait_for_port 127.0.0.1 6334 'Qdrant'

trap cleanup EXIT INT TERM

backend_args=(--env=dev --reload)
if [[ "${MODE}" == '--docs' ]]; then
  backend_args+=(--docs)
fi

log '启动后端热重载'
(
  cd "${REPO_ROOT}"
  uv run --python 3.11 bot "${backend_args[@]}"
) &
backend_pid=$!

log '启动前端 Vite'
(
  cd "${REPO_ROOT}"
  pnpm --dir frontend dev --host 0.0.0.0
) &
frontend_pid=$!

log '开发栈已启动；停止开发依赖容器请执行: uv run poe dev-deps-down'
wait -n "${backend_pid}" "${frontend_pid}"
