#!/usr/bin/env bash
# install.sh — Instalação completa do StudyAgent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[StudyAgent]${NC} $*"; }
warn() { echo -e "${YELLOW}[StudyAgent]${NC} $*"; }
err()  { echo -e "${RED}[StudyAgent]${NC} $*" >&2; }

log "Verificando pré-requisitos..."

# Git
if ! command -v git &>/dev/null; then
    err "Git não encontrado. Instale: sudo apt install git"
    exit 1
fi
log "✓ Git $(git --version | cut -d' ' -f3)"

# Python 3.12+
if ! command -v python3.12 &>/dev/null; then
    err "Python 3.12 não encontrado. Instale: sudo apt install python3.12 python3.12-venv"
    exit 1
fi
log "✓ Python $(python3.12 --version | cut -d' ' -f2)"

# Node.js 18+
if ! command -v node &>/dev/null; then
    err "Node.js não encontrado. Instale via nvm ou apt"
    exit 1
fi
log "✓ Node.js $(node --version)"

# npm
if ! command -v npm &>/dev/null; then
    err "npm não encontrado"
    exit 1
fi
log "✓ npm $(npm --version)"

# Ollama
if ! command -v ollama &>/dev/null; then
    warn "Ollama não encontrado. Instale: curl -fsSL https://ollama.com/install.sh | sh"
else
    log "✓ Ollama $(ollama --version 2>/dev/null || echo 'installed')"
fi

# pip
if ! command -v pip3 &>/dev/null && ! python3.12 -m pip --version &>/dev/null; then
    err "pip não encontrado. Instale: sudo apt install python3-pip"
    exit 1
fi
log "✓ pip OK"

log ""
log "Instalando backend..."
cd "$SCRIPT_DIR/backend"

if [ ! -d ".venv" ]; then
    python3.12 -m venv .venv
    log "✓ Virtualenv criado"
fi

.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
log "✓ Dependências do backend instaladas"

log "Instalando frontend..."
cd "$SCRIPT_DIR/frontend"
npm install --silent
log "✓ Dependências do frontend instaladas"

# Puxar modelos Ollama necessários
if command -v ollama &>/dev/null; then
    log "Verificando modelos Ollama..."
    for model in nomic-embed-text qwen2.5vl:7b llama3.1:latest; do
        if ! ollama list 2>/dev/null | grep -q "$model"; then
            warn "Puxando modelo: $model"
            ollama pull "$model" 2>/dev/null || warn "Falha ao puxar $model (verifique Ollama)"
        else
            log "✓ Modelo $model já instalado"
        fi
    done
fi

# Criar diretórios de dados
mkdir -p "$SCRIPT_DIR/backend/data/memory"
mkdir -p "$SCRIPT_DIR/backend/data/rag"
log "✓ Diretórios de dados criados"

# systemd user services
mkdir -p "$HOME/.config/systemd/user"
if [ ! -f "$HOME/.config/systemd/user/studyagent-api.service" ]; then
    cat > "$HOME/.config/systemd/user/studyagent-api.service" <<EOF
[Unit]
Description=StudyAgent API
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR/backend
ExecStart=$SCRIPT_DIR/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    log "✓ Serviço studyagent-api criado"
fi

if [ ! -f "$HOME/.config/systemd/user/studyagent-web.service" ]; then
    cat > "$HOME/.config/systemd/user/studyagent-web.service" <<EOF
[Unit]
Description=StudyAgent Frontend
After=network.target studyagent-api.service

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR/frontend
ExecStart=$(which npm 2>/dev/null || echo /usr/bin/npm) run dev
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    log "✓ Serviço studyagent-web criado"
fi

systemctl --user daemon-reload 2>/dev/null || true
log "✓ Systemd recarregado"

log ""
log "=========================================="
log "  Instalação concluída!"
log "  Para iniciar: ./start.sh"
log "  Para verificar: ./doctor.sh"
log "=========================================="
