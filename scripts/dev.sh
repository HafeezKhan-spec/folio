#!/usr/bin/env bash
# Start the API on 127.0.0.1:8000 and Vite on 127.0.0.1:5173.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ ! -x "$ROOT/.venv/bin/uvicorn" ]]; then
  echo "Missing .venv. Create it and install the backend first. See the README." >&2
  exit 1
fi

mkdir -p "$(dirname "${FOLIO_DATABASE_PATH:-data/folio.db}")"

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

"$ROOT/.venv/bin/uvicorn" folio.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

(cd "$ROOT/frontend" && npm run dev -- --host 127.0.0.1 --port 5173) &
WEB_PID=$!

wait -n "$API_PID" "$WEB_PID"
status=$?
cleanup
wait || true
exit "$status"
