#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash .devcontainer/setup.sh

export PYTHONPATH="$ROOT/services/backend"
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

pnpm --filter tongpin-web dev --hostname 0.0.0.0 --port 3000