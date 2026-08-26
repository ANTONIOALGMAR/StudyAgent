#!/usr/bin/env bash
# backup.sh — Sistema de backup do StudyAgent
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backages"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[StudyAgent]${NC} $*"; }
warn() { echo -e "${YELLOW}[StudyAgent]${NC} $*"; }

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="studyagent_backup_$TIMESTAMP"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

mkdir -p "$BACKUP_DIR"

log "Criando backup: $BACKUP_NAME"

# Backup do banco de dados
if [ -f "$SCRIPT_DIR/backend/data/memory/studyagent.db" ]; then
    mkdir -p "$BACKUP_PATH/data"
    cp "$SCRIPT_DIR/backend/data/memory/studyagent.db" "$BACKUP_PATH/data/studyagent.db"
    log "✓ Banco de dados copiado"
else
    warn "Banco de dados não encontrado"
fi

# Backup de configurações
if [ -f "$SCRIPT_DIR/config/permissions.json" ]; then
    mkdir -p "$BACKUP_PATH/config"
    cp "$SCRIPT_DIR/config/permissions.json" "$BACKUP_PATH/config/"
    log "✓ Configurações copiadas"
fi

# Backup de índices RAG
if [ -d "$SCRIPT_DIR/backend/data/rag" ]; then
    mkdir -p "$BACKUP_PATH/rag"
    cp -r "$SCRIPT_DIR/backend/data/rag/"*.npz "$BACKUP_PATH/rag/" 2>/dev/null || true
    log "✓ Índices RAG copiados"
fi

# Metadados do backup
cat > "$BACKUP_PATH/metadata.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "version": "$(cd "$SCRIPT_DIR" && git describe --tags --always 2>/dev/null || echo 'unknown')",
  "commit": "$(cd "$SCRIPT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
  "tables": $(cd "$SCRIPT_DIR/backend" && python3.12 -c "import sqlite3; c=sqlite3.connect('data/memory/studyagent.db'); print(len([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]))" 2>/dev/null || echo 0)
}
EOF
log "✓ Metadados salvos"

# Compactar
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME" 2>/dev/null
rm -rf "$BACKUP_PATH"
log "✓ Backup compactado: ${BACKUP_NAME}.tar.gz"

# Manter apenas os últimos 10 backups
cd "$BACKUP_DIR"
ls -t studyagent_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true

# Tamanho do backup
BACKUP_SIZE=$(du -sh "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" 2>/dev/null | cut -f1)
log ""
log "══════════════════════════════════════"
log "  Backup criado com sucesso!"
log "  Arquivo: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
log "  Tamanho: $BACKUP_SIZE"
log "══════════════════════════════════════"
