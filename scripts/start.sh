#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

export PATH="$HOME/ollama/bin:$PATH"
pgrep -x ollama >/dev/null || { nohup ollama serve > /tmp/opencode/ollama.log 2>&1 & sleep 3; }

(cd backend && source .venv/bin/activate && nohup uvicorn app.main:app --port 8000 > /tmp/opencode/api.log 2>&1 &)

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

(cd frontend && npm run dev)
