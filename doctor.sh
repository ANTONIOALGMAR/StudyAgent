#!/usr/bin/env bash
# StudyAgent Doctor
# Diagnóstico completo e somente leitura.
# Não instala, remove ou altera componentes do sistema.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ============================================================
# CONFIGURAÇÃO
# ============================================================

OLLAMA_HOST_STUDY="http://127.0.0.1:11435"
OLLAMA_HOST_SYSTEM="http://127.0.0.1:11434"

PASS=0
WARN=0
FAIL=0

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() {
    echo -e "  ${GREEN}✓${NC} $*"
    PASS=$((PASS + 1))
}

warn() {
    echo -e "  ${YELLOW}⚠${NC} $*"
    WARN=$((WARN + 1))
}

fail() {
    echo -e "  ${RED}✗${NC} $*"
    FAIL=$((FAIL + 1))
}

info() {
    echo -e "  ${CYAN}•${NC} $*"
}

section() {
    echo
    echo -e "${BLUE}━━ $* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

http_ok() {
    curl -fsS --max-time 3 "$1" >/dev/null 2>&1
}

# ============================================================
# CABEÇALHO
# ============================================================

clear 2>/dev/null || true

echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              STUDYAGENT SYSTEM DOCTOR                    ║${NC}"
echo -e "${CYAN}║          Diagnóstico completo da plataforma               ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo

info "Projeto: $SCRIPT_DIR"
info "Data: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ============================================================
# SISTEMA
# ============================================================

section "SISTEMA"

if command -v uname >/dev/null 2>&1; then
    pass "Sistema: $(uname -s) $(uname -m)"
fi

if command -v lsb_release >/dev/null 2>&1; then
    info "Distribuição: $(lsb_release -ds 2>/dev/null || true)"
elif [ -f /etc/os-release ]; then
    . /etc/os-release
    info "Distribuição: ${PRETTY_NAME:-desconhecida}"
fi

if command -v git >/dev/null 2>&1; then
    pass "Git: $(git --version | awk '{print $3}')"
else
    fail "Git não encontrado"
fi

if command -v python3.12 >/dev/null 2>&1; then
    pass "Python: $(python3.12 --version 2>&1 | awk '{print $2}')"
else
    warn "Python 3.12 não encontrado"
fi

if command -v node >/dev/null 2>&1; then
    pass "Node.js: $(node --version)"
else
    warn "Node.js não encontrado"
fi

if command -v npm >/dev/null 2>&1; then
    pass "npm: $(npm --version)"
else
    warn "npm não encontrado"
fi

# ============================================================
# GPU / NVIDIA
# ============================================================

section "GPU / NVIDIA / CUDA"

if command -v nvidia-smi >/dev/null 2>&1; then

    GPU_NAME=$(nvidia-smi \
        --query-gpu=name \
        --format=csv,noheader 2>/dev/null | head -1)

    GPU_MEM=$(nvidia-smi \
        --query-gpu=memory.total \
        --format=csv,noheader 2>/dev/null | head -1)

    DRIVER=$(nvidia-smi \
        --query-gpu=driver_version \
        --format=csv,noheader 2>/dev/null | head -1)

    CUDA_VERSION=$(nvidia-smi 2>/dev/null |
        grep -oE 'CUDA Version: [0-9.]+' |
        head -1 |
        awk '{print $3}')

    pass "NVIDIA GPU: ${GPU_NAME:-detectada}"
    info "VRAM total: ${GPU_MEM:-desconhecida}"
    info "Driver: ${DRIVER:-desconhecido}"

    if [ -n "${CUDA_VERSION:-}" ]; then
        pass "CUDA: $CUDA_VERSION"
    else
        warn "Versão CUDA não identificada"
    fi

    VRAM_INFO=$(nvidia-smi \
        --query-gpu=memory.used,memory.free \
        --format=csv,noheader 2>/dev/null | head -1)

    info "VRAM: ${VRAM_INFO:-indisponível}"

else
    warn "nvidia-smi não encontrado"
fi

# ============================================================
# OLLAMA BINÁRIOS
# ============================================================

section "OLLAMA — BINÁRIOS"

OLLAMA_BIN="$(command -v ollama 2>/dev/null || true)"

if [ -n "$OLLAMA_BIN" ]; then
    pass "Ollama no PATH: $OLLAMA_BIN"

    OLLAMA_VERSION_OUTPUT="$("$OLLAMA_BIN" --version 2>&1 || true)"

    if echo "$OLLAMA_VERSION_OUTPUT" | grep -q "ollama version"; then
        info "$OLLAMA_VERSION_OUTPUT"
    else
        warn "Não foi possível determinar a versão do Ollama"
    fi
else
    fail "Ollama não encontrado no PATH"
fi

if [ -x "$HOME/ollama/bin/ollama" ]; then
    LOCAL_VERSION="$("$HOME/ollama/bin/ollama" --version 2>&1 || true)"
    pass "Ollama StudyAgent: $HOME/ollama/bin/ollama"
    info "$LOCAL_VERSION"
else
    fail "Binário $HOME/ollama/bin/ollama não encontrado"
fi

if [ -x "/usr/local/bin/ollama" ]; then
    SYSTEM_VERSION="$(/usr/local/bin/ollama --version 2>&1 || true)"
    pass "Ollama sistema: /usr/local/bin/ollama"
    info "$SYSTEM_VERSION"
else
    warn "/usr/local/bin/ollama não encontrado"
fi

# ============================================================
# OLLAMA STUDYAGENT — 11435
# ============================================================

section "OLLAMA — STUDYAGENT :11435"

if http_ok "$OLLAMA_HOST_STUDY/api/version"; then

    STUDY_VERSION=$(curl -fsS --max-time 3 \
        "$OLLAMA_HOST_STUDY/api/version" |
        sed -n 's/.*"version":"\([^"]*\)".*/\1/p')

    pass "Servidor respondendo em 127.0.0.1:11435"
    pass "Versão servidor: ${STUDY_VERSION:-desconhecida}"

else
    fail "Ollama StudyAgent não responde em 127.0.0.1:11435"
fi

# ============================================================
# OLLAMA SISTEMA — 11434
# ============================================================

section "OLLAMA — SISTEMA :11434"

if http_ok "$OLLAMA_HOST_SYSTEM/api/version"; then

    SYSTEM_SERVER_VERSION=$(curl -fsS --max-time 3 \
        "$OLLAMA_HOST_SYSTEM/api/version" |
        sed -n 's/.*"version":"\([^"]*\)".*/\1/p')

    pass "Servidor respondendo em 127.0.0.1:11434"
    info "Versão servidor: ${SYSTEM_SERVER_VERSION:-desconhecida}"

else
    info "Nenhum Ollama respondendo em 127.0.0.1:11434"
fi

# ============================================================
# PROCESSOS / PORTAS
# ============================================================

section "PROCESSOS / PORTAS"

if pgrep -x ollama >/dev/null 2>&1; then
    pass "Processos Ollama detectados"
    ps -eo pid,user,cmd | grep '[o]llama serve' || true
else
    warn "Nenhum processo Ollama detectado"
fi

if command -v ss >/dev/null 2>&1; then

    if ss -ltn 2>/dev/null | grep -q '127.0.0.1:11435'; then
        pass "Porta 11435: LISTEN"
    else
        fail "Porta 11435: fechada"
    fi

    if ss -ltn 2>/dev/null | grep -q '127.0.0.1:11434'; then
        pass "Porta 11434: LISTEN"
    else
        info "Porta 11434: fechada"
    fi

    if ss -ltn 2>/dev/null | grep -q ':8000'; then
        pass "Porta 8000: LISTEN"
    else
        warn "Porta 8000: fechada"
    fi

    if ss -ltn 2>/dev/null | grep -q ':5173'; then
        pass "Porta 5173: LISTEN"
    else
        warn "Porta 5173: fechada"
    fi

fi

# ============================================================
# MODELOS OLLAMA
# ============================================================

section "MODELOS — OLLAMA STUDYAGENT"

if http_ok "$OLLAMA_HOST_STUDY/api/version"; then

    MODELS_JSON=$(curl -fsS --max-time 5 \
        "$OLLAMA_HOST_STUDY/api/tags" 2>/dev/null || true)

    check_model() {
        local MODEL="$1"

        if echo "$MODELS_JSON" | grep -q "\"name\":\"$MODEL\""; then
            pass "Modelo: $MODEL"
        elif echo "$MODELS_JSON" | grep -q "\"name\":\"${MODEL}:latest\""; then
            pass "Modelo: ${MODEL}:latest"
        elif echo "$MODELS_JSON" | grep -q "\"name\":\"${MODEL}:"; then
            pass "Modelo: $MODEL"
        else
            warn "Modelo ausente: $MODEL"
        fi
    }

    check_model "llama3.1"
    check_model "qwen2.5vl:7b"
    check_model "qwen2.5:7b"
    check_model "qwen2.5-coder:7b"
    check_model "nomic-embed-text"
    check_model "llama3"

else
    warn "Não foi possível consultar modelos"
fi

# ============================================================
# TESTE DE GERAÇÃO
# ============================================================

section "TESTE FUNCIONAL — TEXTO"

if http_ok "$OLLAMA_HOST_STUDY/api/version"; then

    TEXT_START=$(date +%s%3N)

    TEXT_RESPONSE=$(curl -fsS \
        --max-time 30 \
        -X POST \
        "$OLLAMA_HOST_STUDY/api/generate" \
        -H 'Content-Type: application/json' \
        -d '{
            "model":"llama3.1",
            "prompt":"Responda exatamente: TESTE OK",
            "stream":false
        }' 2>/dev/null || true)

    TEXT_END=$(date +%s%3N)

    TEXT_TIME=$((TEXT_END - TEXT_START))

    if echo "$TEXT_RESPONSE" | grep -qi "TESTE OK"; then
        pass "llama3.1 geração funcional (${TEXT_TIME} ms)"
    elif [ -n "$TEXT_RESPONSE" ]; then
        warn "llama3.1 respondeu, mas resultado inesperado"
        info "$TEXT_RESPONSE"
    else
        fail "Falha na geração com llama3.1"
    fi

else
    warn "Teste de texto ignorado: Ollama offline"
fi

# ============================================================
# TESTE DE EMBEDDING
# ============================================================

section "TESTE FUNCIONAL — EMBEDDINGS"

if http_ok "$OLLAMA_HOST_STUDY/api/version"; then

    EMBED_RESPONSE=$(curl -fsS \
        --max-time 30 \
        -X POST \
        "$OLLAMA_HOST_STUDY/api/embed" \
        -H 'Content-Type: application/json' \
        -d '{
            "model":"nomic-embed-text",
            "input":"StudyAgent teste de embedding"
        }' 2>/dev/null || true)

    if echo "$EMBED_RESPONSE" | grep -q '"embeddings"'; then
        pass "nomic-embed-text: embeddings funcionando"
    else
        warn "nomic-embed-text: teste falhou"
    fi

fi

# ============================================================
# BACKEND
# ============================================================

section "BACKEND"

if [ -d "$SCRIPT_DIR/backend" ]; then
    pass "Diretório backend encontrado"
else
    fail "Diretório backend não encontrado"
fi

if [ -x "$SCRIPT_DIR/backend/.venv/bin/python" ]; then
    pass "Virtualenv Python encontrado"
else
    fail "Virtualenv Python não encontrado"
fi

if [ -x "$SCRIPT_DIR/backend/.venv/bin/uvicorn" ]; then
    pass "Uvicorn instalado"
else
    fail "Uvicorn não encontrado"
fi

if [ -f "$SCRIPT_DIR/backend/.env" ]; then
    pass "backend/.env encontrado"

    CONFIG_OLLAMA=$(grep '^OLLAMA_HOST=' \
        "$SCRIPT_DIR/backend/.env" 2>/dev/null |
        head -1 || true)

    info "$CONFIG_OLLAMA"

    if echo "$CONFIG_OLLAMA" | grep -q ':11435'; then
        pass "Backend configurado para Ollama :11435"
    else
        warn "Backend não está configurado explicitamente para :11435"
    fi

else
    warn "backend/.env não encontrado"
fi

# ============================================================
# BANCO
# ============================================================

section "BANCO DE DADOS"

DB="$SCRIPT_DIR/data/memory/studyagent.db"

if [ -f "$DB" ]; then

    if command -v python3.12 >/dev/null 2>&1; then

        TABLES=$(python3.12 - "$DB" <<'PY' 2>/dev/null
import sqlite3
import sys

db = sys.argv[1]

try:
    conn = sqlite3.connect(db)
    count = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0]
    print(count)
except Exception:
    print(0)
PY
)

        if [ "$TABLES" -gt 0 ]; then
            pass "SQLite encontrado: $TABLES tabelas"
        else
            warn "SQLite encontrado, mas sem tabelas"
        fi

    fi

else
    warn "Banco SQLite ainda não encontrado"
fi

# ============================================================
# VISION
# ============================================================

section "VISION ENGINE"

if command -v tesseract >/dev/null 2>&1; then
    pass "Tesseract OCR: $(tesseract --version 2>&1 | head -1)"
else
    warn "Tesseract OCR não encontrado"
fi

if [ -x "$SCRIPT_DIR/backend/.venv/bin/python" ]; then

    if "$SCRIPT_DIR/backend/.venv/bin/python" -c "import mss" >/dev/null 2>&1; then
        pass "Python mss: disponível"
    else
        warn "Python mss: ausente"
    fi

    if "$SCRIPT_DIR/backend/.venv/bin/python" -c "import ollama" >/dev/null 2>&1; then
        pass "Python Ollama SDK: disponível"
    else
        warn "Python Ollama SDK: ausente"
    fi

fi

# ============================================================
# API
# ============================================================

section "BACKEND API"

if http_ok "http://127.0.0.1:8000/api/health"; then
    pass "API Health: OK"

    API_HEALTH=$(curl -fsS \
        --max-time 5 \
        http://127.0.0.1:8000/api/health 2>/dev/null || true)

    [ -n "$API_HEALTH" ] && info "$API_HEALTH"
else
    warn "API não responde em :8000"
fi

SCREEN_DIAG=$(curl -fsS \
    --connect-timeout 2 \
    --max-time 15 \
    http://127.0.0.1:8000/api/screen/diagnostics \
    2>/dev/null || true)

if [ -n "$SCREEN_DIAG" ]; then

    pass "Screen Diagnostics: API OK"

    if echo "$SCREEN_DIAG" | grep -q '"screen_capture":true'; then
        pass "Screen Capture: OK"
    else
        warn "Screen Capture não validada"
    fi

    if echo "$SCREEN_DIAG" | grep -q '"ocr_test":true'; then
        pass "OCR Engine: OK"
    else
        warn "OCR Engine não validada"
    fi

    if echo "$SCREEN_DIAG" | grep -q '"vision_test":true'; then
        pass "Vision Engine: OK"
    else
        warn "Vision Engine não validada"
    fi

    if echo "$SCREEN_DIAG" | grep -q '"ollama_available":true'; then
        pass "Vision Ollama: OK"
    else
        warn "Vision Ollama não disponível"
    fi

    if echo "$SCREEN_DIAG" | grep -q '"screen":true'; then
        pass "Permissão de tela: OK"
    else
        warn "Permissão de tela não confirmada"
    fi

    if echo "$SCREEN_DIAG" | grep -q '"camera":true'; then
        pass "Permissão de câmera: OK"
    else
        warn "Permissão de câmera não confirmada"
    fi

    MONITOR_COUNT=$(echo "$SCREEN_DIAG" |
        sed -n 's/.*"monitor_count":\([0-9]*\).*/\1/p')

    if [ -n "$MONITOR_COUNT" ] && [ "$MONITOR_COUNT" -gt 0 ] 2>/dev/null; then
        pass "Monitores detectados: $MONITOR_COUNT"
    else
        warn "Nenhum monitor detectado"
    fi

else
    warn "Endpoint de diagnóstico de tela não respondeu"
fi

# ============================================================
# FRONTEND
# ============================================================

section "FRONTEND"

if [ -d "$SCRIPT_DIR/frontend" ]; then
    pass "Diretório frontend encontrado"
else
    fail "Diretório frontend não encontrado"
fi

if [ -f "$SCRIPT_DIR/frontend/package.json" ]; then
    pass "package.json encontrado"
else
    fail "package.json não encontrado"
fi

if [ -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    pass "node_modules encontrado"
else
    warn "node_modules não encontrado"
fi

if http_ok "http://127.0.0.1:5173"; then
    pass "Frontend respondendo em :5173"
else
    warn "Frontend não responde em :5173"
fi

# ============================================================
# SYSTEMD USER
# ============================================================

section "SYSTEMD — STUDYAGENT"

check_service() {
    local SERVICE="$1"

    if systemctl --user is-active --quiet "$SERVICE" 2>/dev/null; then
        pass "$SERVICE: ativo"
    else
        warn "$SERVICE: inativo"
    fi
}

check_service "studyagent-ollama.service"
check_service "studyagent-api.service"
check_service "studyagent-web.service"

# ============================================================
# CONFIGURAÇÃO DOS SERVIÇOS
# ============================================================

section "CONFIGURAÇÃO OLLAMA — STUDYAGENT"

if systemctl --user cat studyagent-ollama.service >/dev/null 2>&1; then

    UNIT_CONFIG=$(systemctl --user cat studyagent-ollama.service 2>/dev/null || true)

    if echo "$UNIT_CONFIG" | grep -q 'OLLAMA_HOST=127.0.0.1:11435'; then
        pass "systemd Ollama configurado em :11435"
    else
        warn "systemd Ollama não declara explicitamente :11435"
    fi

    if echo "$UNIT_CONFIG" | grep -q 'OLLAMA_MODELS='; then
        pass "Diretório de modelos configurado"
    else
        warn "OLLAMA_MODELS não declarado no serviço"
    fi

fi

# ============================================================
# GIT
# ============================================================

section "GIT / PROJETO"

if [ -d "$SCRIPT_DIR/.git" ]; then

    BRANCH=$(git branch --show-current 2>/dev/null || true)
    STATUS=$(git status --short 2>/dev/null || true)

    pass "Repositório Git encontrado"
    info "Branch: ${BRANCH:-desconhecida}"

    if [ -z "$STATUS" ]; then
        pass "Working tree limpo"
    else
        warn "Existem alterações locais"
        echo "$STATUS" | head -20
    fi

else
    warn "Repositório Git não encontrado"
fi

# ============================================================
# RESUMO
# ============================================================

echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                       RESULTADO                           ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo

echo -e "  ${GREEN}✓ PASSOU : $PASS${NC}"
echo -e "  ${YELLOW}⚠ AVISOS : $WARN${NC}"
echo -e "  ${RED}✗ FALHAS : $FAIL${NC}"

echo

TOTAL=$((PASS + WARN + FAIL))

if [ "$TOTAL" -gt 0 ]; then
    SCORE=$((PASS * 100 / TOTAL))
    info "Saúde aproximada: ${SCORE}%"
fi

echo

if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
    echo -e "${GREEN}✓ StudyAgent completamente saudável.${NC}"
elif [ "$FAIL" -eq 0 ]; then
    echo -e "${YELLOW}⚠ StudyAgent operacional, mas existem avisos para revisar.${NC}"
else
    echo -e "${RED}✗ StudyAgent possui componentes que precisam de atenção.${NC}"
fi

echo
echo "Diagnóstico concluído."
echo

exit "$FAIL"
