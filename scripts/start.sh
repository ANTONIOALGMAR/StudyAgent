#!/usr/bin/env bash
set -e
SCRIPT="$(readlink -f "$0")"
ROOT="$(cd "$(dirname "$SCRIPT")/.." && pwd)"
export PATH="$HOME/ollama/bin:$PATH"
mkdir -p /tmp/opencode

up() { curl -s --max-time 2 "http://localhost:$1$2" > /dev/null 2>&1; }

if ! up 11434 /api/version; then
  nohup ollama serve > /tmp/opencode/ollama.log 2>&1 &
fi

if ! curl -s --max-time 2 http://localhost:8000/api/health 2>/dev/null | grep -q ok; then
  (cd "$ROOT/backend" && nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/opencode/api.log 2>&1 &)
fi

if ! up 5173; then
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    (cd "$ROOT/frontend" && npm install --silent)
  fi
  (cd "$ROOT/frontend" && nohup npx vite --port 5173 > /tmp/opencode/vite.log 2>&1 &)
fi
