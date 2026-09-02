#!/usr/bin/env bash
# stop.sh — Para os serviços do StudyAgent
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[StudyAgent]${NC} $*"; }
warn() { echo -e "${YELLOW}[StudyAgent]${NC} $*"; }

log "Parando StudyAgent..."

# Parar via systemd
if systemctl --user is-active studyagent-api &>/dev/null; then
    systemctl --user stop studyagent-api
    log "✓ studyagent-api parado"
fi

if systemctl --user is-active studyagent-web &>/dev/null; then
    systemctl --user stop studyagent-web
    log "✓ studyagent-web parado"
fi

# Parar PIDs diretos (fallback)
for pidfile in "$SCRIPT_DIR/.api.pid" "$SCRIPT_DIR/.web.pid"; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            log "✓ Processo $PID parado"
        fi
        rm -f "$pidfile"
    fi
done

# Verificar se há processos uvicorn restantes (restrito a este projeto para
# não derrubar instâncias de outros projetos na mesma máquina)
UVICORN_PIDS=$(pgrep -f "$SCRIPT_DIR/backend/.*uvicorn app.main:app" 2>/dev/null || true)
if [ -n "$UVICORN_PIDS" ]; then
    warn "Encontrados processos uvicorn restantes (estudo): $UVICORN_PIDS"
    echo "$UVICORN_PIDS" | xargs kill 2>/dev/null || true
    log "✓ Processos uvicorn parados"
fi

log ""
log "StudyAgent parado com sucesso."
