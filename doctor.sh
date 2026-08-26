#!/usr/bin/env bash
# doctor.sh — Verificação de saúde do StudyAgent
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
WARN=0
FAIL=0

check_pass() { echo -e "  ${GREEN}✓${NC} $*"; PASS=$((PASS+1)); }
check_warn() { echo -e "  ${YELLOW}⚠${NC} $*"; WARN=$((WARN+1)); }
check_fail() { echo -e "  ${RED}✗${NC} $*"; FAIL=$((FAIL+1)); }

echo "╔══════════════════════════════════════╗"
echo "║     StudyAgent — Health Check        ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Sistema ────────────────────────────────────────────────────────────────────
echo "── Sistema ──"

command -v git &>/dev/null && check_pass "Git $(git --version | cut -d' ' -f3)" || check_fail "Git não encontrado"

command -v python3.12 &>/dev/null && check_pass "Python $(python3.12 --version | cut -d' ' -f2)" || check_fail "Python 3.12 não encontrado"

command -v node &>/dev/null && check_pass "Node.js $(node --version)" || check_fail "Node.js não encontrado"

command -v ollama &>/dev/null && check_pass "Ollama instalado" || check_warn "Ollama não encontrado (necessário para modelos)"

echo ""

# ── Backend ────────────────────────────────────────────────────────────────────
echo "── Backend ──"

cd "$SCRIPT_DIR/backend"

if [ -f ".venv/bin/python" ]; then
    check_pass "Virtualenv existe"
else
    check_fail "Virtualenv não encontrado (execute ./install.sh)"
fi

if [ -f ".venv/bin/uvicorn" ]; then
    check_pass "uvicorn instalado"
else
    check_fail "uvicorn não encontrado"
fi

if [ -f ".venv/bin/fastapi" ]; then
    check_pass "fastapi instalado"
else
    check_fail "fastapi não encontrado"
fi

# Verificar tabelas SQLite
if [ -f "data/memory/studyagent.db" ]; then
    TABLES=$(python3.12 -c "import sqlite3; c=sqlite3.connect('data/memory/studyagent.db'); print(len([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]))" 2>/dev/null || echo "0")
    if [ "$TABLES" -ge 19 ]; then
        check_pass "SQLite com $TABLES tabelas"
    else
        check_warn "SQLite com apenas $TABLES tabelas (esperado ≥19)"
    fi
else
    check_warn "Banco de dados não encontrado (será criado ao iniciar)"
fi

# Verificar modelos Ollama
if command -v ollama &>/dev/null; then
    for model in nomic-embed-text llama3.1:latest; do
        if ollama list 2>/dev/null | grep -q "$model"; then
            check_pass "Modelo $model disponível"
        else
            check_warn "Modelo $model não encontrado"
        fi
    done
    # Verificar qwen2.5vl (pode ter variações)
    if ollama list 2>/dev/null | grep -q "qwen"; then
        check_pass "Modelo qwen disponível"
    else
        check_warn "Modelo qwen2.5vl não encontrado"
    fi
fi

echo ""

# ── Frontend ───────────────────────────────────────────────────────────────────
echo "── Frontend ──"

cd "$SCRIPT_DIR/frontend"

if [ -d "node_modules" ]; then
    check_pass "node_modules existe"
else
    check_fail "node_modules não encontrado (execute ./install.sh)"
fi

if [ -f "package.json" ]; then
    check_pass "package.json existe"
else
    check_fail "package.json não encontrado"
fi

echo ""

# ── Serviços ──────────────────────────────────────────────────────────────────
echo "── Serviços ──"

if systemctl --user is-active studyagent-api &>/dev/null; then
    check_pass "studyagent-api: ativo"
else
    check_warn "studyagent-api: inativo"
fi

if systemctl --user is-active studyagent-web &>/dev/null; then
    check_pass "studyagent-web: ativo"
else
    check_warn "studyagent-web: inativo"
fi

# Verificar porta 8000
if ss -tlnp 2>/dev/null | grep -q ":8000"; then
    check_pass "Porta 8000: aberta"
else
    check_warn "Porta 8000: fechada"
fi

# Verificar porta 5173
if ss -tlnp 2>/dev/null | grep -q ":5173"; then
    check_pass "Porta 5173: aberta"
else
    check_warn "Porta 5173: fechada"
fi

# Health check HTTP
if curl -sf http://localhost:8000/api/health &>/dev/null; then
    check_pass "API respondendo em localhost:8000"
else
    check_warn "API não responde em localhost:8000"
fi

echo ""

# ── Resumo ────────────────────────────────────────────────────────────────────
echo "══════════════════════════════════════"
echo -e "  ${GREEN}✓ $PASS passou${NC}  ${YELLOW}⚠ $WARN avisos${NC}  ${RED}✗ $FAIL falhou${NC}"
echo "══════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo -e "${RED}Alguns verificação(s) falharam. Execute ./install.sh para corrigir.${NC}"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}Alguns avisos. Verifique acima.${NC}"
fi
