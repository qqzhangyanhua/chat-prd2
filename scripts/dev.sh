#!/usr/bin/env bash
set -euo pipefail

SKIP_MIGRATE=false
if [[ "${1:-}" == "--skip-migrate" ]]; then
    SKIP_MIGRATE=true
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$PROJECT_ROOT/apps/api"
VENV_ACTIVATE="$API_DIR/.venv/bin/activate"

step() { echo -e "\033[0;36m[dev] $1\033[0m"; }

step "Project root: $PROJECT_ROOT"

step "Syncing Python dependencies via uv"
cd "$API_DIR"
uv sync
cd "$PROJECT_ROOT"

if [[ "$SKIP_MIGRATE" == false ]]; then
    step "Running alembic upgrade head"
    source "$VENV_ACTIVATE"
    cd "$API_DIR"
    "$API_DIR/.venv/bin/alembic" upgrade head
    cd "$PROJECT_ROOT"
else
    step "Skipping database migration"
fi

step "Starting API server (background)"
source "$VENV_ACTIVATE"
python -m uvicorn app.main:app --reload --app-dir "$API_DIR" &
API_PID=$!

step "Starting web dev server (foreground)"
cd "$PROJECT_ROOT"
pnpm dev:web &
WEB_PID=$!

trap "kill $API_PID $WEB_PID 2>/dev/null; exit" INT TERM

step "API (PID $API_PID) and Web (PID $WEB_PID) started. Press Ctrl+C to stop."
wait
