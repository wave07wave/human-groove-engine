#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv312/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment is missing. Follow the README setup steps first."
  exit 1
fi
if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run npm install in frontend/."
  exit 1
fi

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd "$ROOT_DIR/backend" && "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd "$ROOT_DIR/frontend" && npm run dev -- --host 127.0.0.1) &
FRONTEND_PID=$!
wait
