#!/usr/bin/env bash
# start.sh — Inicia os serviços do StudyAgent
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[StudyAgent]${NC} $*"; }
warn() { echo -e "${YELLOW}[StudyAgent]${NC} $*"; }

log "Iniciando StudyAgent..."

# Garantir que Ollama esteja rodando
if command -v ollama &>/dev/null; then
    if ! pgrep -x ollama &>/dev/null; then
        log "Iniciando Ollama..."
        ollama serve &>/dev/null &
        sleep 2
    fi
fi

# Iniciar backend
log "Iniciando API (backend)..."
systemctl --user start studyagent-api 2>/dev/null || {
    warn "systemd não disponível, iniciando diretamente..."
    cd "$SCRIPT_DIR/backend"
    .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
    echo $! > "$SCRIPT_DIR/.api.pid"
    log "API iniciada com PID $(cat "$SCRIPT_DIR/.api.pid")"
}

# Aguardar API ficar pronta
log "Aguardando API..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/api/health &>/dev/null; then
        log "✓ API pronta em http://localhost:8000"
        break
    fi
    sleep 1
done

# Iniciar frontend
log "Iniciando Frontend..."
systemctl --user start studyagent-web 2>/dev/null || {
    warn "systemd não disponível, iniciando diretamente..."
    cd "$SCRIPT_DIR/frontend"
    npm run dev &
    echo $! > "$SCRIPT_DIR/.web.pid"
    log "Frontend iniciado com PID $(cat "$SCRIPT_DIR/.web.pid")"
}

sleep 2

log ""
log "══════════════════════════════════════"
log "  StudyAgent rodando!"
log "  API:   http://localhost:8000"
log "  Web:   http://localhost:5173"
log "══════════════════════════════════════"
