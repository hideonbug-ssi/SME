#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BE_DIR="$ROOT/backend"
FE_DIR="$ROOT/frontend"
VENV="$BE_DIR/.venv"

BE="\033[0;34m[be]\033[0m"
FE="\033[0;32m[fe]\033[0m"
INFO="\033[0;33m[dev]\033[0m"

# ── bootstrap backend ──────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo -e "$INFO creating Python venv..."
  python3 -m venv "$VENV"
fi

if [ ! -f "$VENV/lib/python*/site-packages/uvicorn/__init__.py" ] 2>/dev/null || \
   ! "$VENV/bin/pip" show uvicorn &>/dev/null; then
  echo -e "$INFO installing backend dependencies..."
  "$VENV/bin/pip" install -q -r "$BE_DIR/requirements.txt"
fi

# ── bootstrap frontend ─────────────────────────────────────────────
if [ ! -d "$FE_DIR/node_modules" ]; then
  echo -e "$INFO installing frontend dependencies..."
  (cd "$FE_DIR" && npm install)
fi

# ── start services ─────────────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "$INFO shutting down..."
  kill "$BE_PID" "$FE_PID" 2>/dev/null || true
  wait "$BE_PID" "$FE_PID" 2>/dev/null || true
  echo -e "$INFO done."
}
trap cleanup INT TERM

(cd "$BE_DIR" && "$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 --reload 2>&1 \
  | while IFS= read -r line; do printf "${BE} %s\n" "$line"; done) &
BE_PID=$!

(cd "$FE_DIR" && npm run dev 2>&1 \
  | while IFS= read -r line; do printf "${FE} %s\n" "$line"; done) &
FE_PID=$!

echo -e "$INFO backend  → http://localhost:8000"
echo -e "$INFO frontend → http://localhost:5173"
echo -e "$INFO Ctrl+C to stop both."
echo ""

wait "$BE_PID" "$FE_PID"
