#!/usr/bin/env bash
# update.sh — Atualiza o StudyAgent do repositório git
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[StudyAgent]${NC} $*"; }
warn() { echo -e "${YELLOW}[StudyAgent]${NC} $*"; }
err()  { echo -e "${RED}[StudyAgent]${NC} $*" >&2; }

log "Atualizando StudyAgent..."

cd "$SCRIPT_DIR"

# Verificar se é um repositório git
if [ ! -d ".git" ]; then
    err "Não é um repositório git. Execute ./install.sh primeiro."
    exit 1
fi

# Backup antes de atualizar
log "Criando backup antes da atualização..."
"$SCRIPT_DIR/backup.sh" 2>/dev/null || warn "Falha ao criar backup"

# Parar serviços
log "Parando serviços..."
"$SCRIPT_DIR/stop.sh" 2>/dev/null || true

# Pull
log "Baixando atualizações..."
# Guarda alterações locais de forma restauravel (evita perda silenciosa de
# trabalho de devs paralelos). Sem stash silencioso descartado.
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    warn "Alterações locais detectadas. Movidas para stash e serão restauradas após o pull."
    git stash push -m "update.sh auto $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    STASHED=1
else
    STASHED=0
fi
git pull origin main || {
    err "Falha ao fazer pull. Verifique a conexão."
    if [ "$STASHED" = "1" ]; then
        git stash pop 2>/dev/null || warn "Falha ao restaurar stash (resolva manualmente: git stash list)"
    fi
    exit 1
}
if [ "$STASHED" = "1" ]; then
    git stash pop 2>/dev/null || warn "Conflito ao restaurar alterações locais. Resolva e rode: git stash list / git stash pop"
fi

# Atualizar dependências
log "Atualizando dependências do backend..."
cd "$SCRIPT_DIR/backend"
if [ -f ".venv/bin/pip" ]; then
    .venv/bin/pip install -r requirements.txt -q 2>/dev/null || warn "Falha ao atualizar dependências do backend"
fi

log "Atualizando dependências do frontend..."
cd "$SCRIPT_DIR/frontend"
if [ -d "node_modules" ]; then
    npm install --silent 2>/dev/null || warn "Falha ao atualizar dependências do frontend"
fi

# Verificar migrações do banco
log "Verificando banco de dados..."
cd "$SCRIPT_DIR/backend"
if [ -f ".venv/bin/python" ]; then
    .venv/bin/python -c "
from app.db import get_connection
conn = get_connection()
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print(f'Tabelas: {len(tables)}')
" 2>/dev/null || warn "Falha ao verificar banco"
fi

# Reiniciar
log "Reiniciando serviços..."
cd "$SCRIPT_DIR"
"$SCRIPT_DIR/start.sh" 2>/dev/null || warn "Falha ao reiniciar"

log ""
log "══════════════════════════════════════"
log "  Atualização concluída!"
log "  Commits recentes:"
git log --oneline -5
log "══════════════════════════════════════"
