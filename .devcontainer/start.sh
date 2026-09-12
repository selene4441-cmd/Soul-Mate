#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p .devcontainer/logs

stop_service() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

stop_service .devcontainer/backend.pid
stop_service .devcontainer/web.pid

export PYTHONPATH="$ROOT/services/backend"
nohup .venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  > .devcontainer/logs/backend.log 2>&1 &
echo $! > .devcontainer/backend.pid

pnpm --filter tongpin-web dev --hostname 0.0.0.0 --port 3000 \
  > .devcontainer/logs/web.log 2>&1 &
echo $! > .devcontainer/web.pid

for _ in $(seq 1 60); do
  if curl --silent --fail http://127.0.0.1:8000/api/v1/health >/dev/null \
    && curl --silent --fail http://127.0.0.1:3000 >/dev/null; then
    echo "同频已启动：打开 Ports 面板中的 3000 端口预览。"
    exit 0
  fi
  sleep 1
done

echo "启动超时。查看 .devcontainer/logs/backend.log 和 web.log。" >&2
exit 1