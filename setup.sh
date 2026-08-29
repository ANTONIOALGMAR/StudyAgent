#!/usr/bin/env bash
# ============================================================
#  StudyAgent — SETUP MASTER (tudo em um clique)
# ------------------------------------------------------------
#  Baixa o StudyAgent do GitHub e instala/configura TUDO
#  automaticamente em qualquer máquina (Linux / macOS / WSL),
#  SEM intervenção humana além de digitar a senha do sudo
#  (quando necessário para instalar pacotes do sistema).
#
#  Uso direto do GitHub (recomendado):
#    bash -c "$(curl -fsSL https://raw.githubusercontent.com/ANTONIOALGMAR/StudyAgent/main/setup.sh)"
#
#  Ou após baixar:
#    curl -fsSL -o setup.sh https://raw.githubusercontent.com/ANTONIOALGMAR/StudyAgent/main/setup.sh
#    bash setup.sh
# ============================================================
set -uo pipefail

# ── Configuração (edite se precisar) ──────────────────────────
REPO_URL="https://github.com/ANTONIOALGMAR/StudyAgent.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/StudyAgent}"
BRANCH="main"
INSTALL_PREREQS="yes"          # instala git/python/node/ollama/etc do sistema
INSTALL_OLLAMA="yes"           # tenta instalar o Ollama localmente
PULL_MODELS="yes"              # baixa os modelos Ollama
AUTO_START="yes"               # inicia os serviços após instalar
OPEN_BROWSER="yes"             # abre o navegador ao final
OLLAMA_MODELS=(nomic-embed-text qwen2.5vl:7b llama3.1:latest)
# benchmarks/serviços ligados antes de prosseguir
API_URL="http://localhost:8000"
WEB_URL="http://localhost:5173"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()  { echo -e "  ${GREEN}✓${NC} $*"; }
warn(){ echo -e "  ${YELLOW}⚠${NC} $*"; }
err() { echo -e "  ${RED}✗${NC} $*"; }
sec() { echo; echo -e "${BLUE}── $* ──${NC}"; }

LOG_FILE="${TMPDIR:-/tmp}/studyagent-setup-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

trap 'echo; err "Falhou na etapa: $CURRENT_STEP"; err "Veja o log: $LOG_FILE"; exit 1' ERR
CURRENT_STEP="inicialização"

# ── Detecção de plataforma ────────────────────────────────────
detect_os() {
  if grep -qi microsoft /proc/version 2>/dev/null; then
    PLATFORM="wsl"
  elif [ "$(uname -s)" = "Darwin" ]; then
    PLATFORM="macos"
  elif [ -f /etc/os-release ]; then
    . /etc/os-release
    PLATFORM="linux"; DISTRO_ID="$ID"
  else
    PLATFORM="linux"; DISTRO_ID="unknown"
  fi
}
detect_os

pkg_mgr() {
  case "$PLATFORM" in
    macos) echo "brew" ;;
    *) if   command -v apt-get &>/dev/null; then echo "apt";
       elif command -v dnf      &>/dev/null; then echo "dnf";
       elif command -v pacman   &>/dev/null; then echo "pacman";
       elif command -v zypper   &>/dev/null; then echo "zypper";
       else echo "none"; fi ;;
  esac
}

# ── Helpers sudo ──────────────────────────────────────────────
SUDO=""
need_sudo() {
  if [ "$(id -u)" -eq 0 ]; then SUDO=""; return 1; fi
  SUDO="sudo"; return 0
}
run_priv() { # executa com privilégios se necessário
  if [ -n "$SUDO" ]; then $SUDO "$@"; else "$@"; fi
}

install_pkgs() { # $1 = lista
  case "$(pkg_mgr)" in
    apt)
      run_priv apt-get update -y >/dev/null 2>&1
      run_priv apt-get install -y --no-install-recommends $1 >/dev/null 2>&1 ;;
    dnf)
      run_priv dnf install -y $1 >/dev/null 2>&1 ;;
    pacman)
      run_priv pacman -S --noconfirm --needed $1 >/dev/null 2>&1 ;;
    zypper)
      run_priv zypper --non-interactive install -y $1 >/dev/null 2>&1 ;;
    brew)
      brew install $1 >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}

command_exists() { command -v "$1" &>/dev/null; }

# ==============================================================
#  ETAPA 0 — Pré-requisitos do sistema
# ==============================================================
CURRENT_STEP="instalar pré-requisitos do sistema"
if [ "$INSTALL_PREREQS" = "yes" ]; then
  sec "Pré-requisitos do sistema ($PLATFORM / $(pkg_mgr))"
  need_sudo
  if [ -n "$SUDO" ]; then
    ok "Elevando para instalar pacotes (será pedida a senha do usuário)..."
    $SUDO -v 2>/dev/null && ok "Privilégios sudo obtidos" || warn "Uso de sudo limitado; pré-requisitos podem falhar"
  fi

  # Git
  if ! command_exists git; then
    install_pkgs "git" && ok "Git instalado" || err "Falha ao instalar Git"
  else
    ok "Git presente ($(git --version | cut -d' ' -f3))"
  fi

  # Python 3.12+ (fallback: qualquer python3 >= 3.10)
  PYCMD=""
  for c in python3.12 python3.13 python3.11 python3.10 python3; do
    if command_exists "$c"; then
      if $c -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null; then
        PYCMD="$c"; break
      fi
    fi
  done
  if [ -z "$PYCMD" ]; then
    case "$(pkg_mgr)" in
      apt) install_pkgs "python3 python3-venv python3-pip" && PYCMD=python3 ;;
      dnf) install_pkgs "python3 python3-pip" && PYCMD=python3 ;;
      *)   PYCMD=python3 ;;
    esac
  fi
  if command_exists "$PYCMD"; then
    ok "Python presente ($($PYCMD --version 2>&1 | tr -d '\n'))"
    install_pkgs "python3-venv python3-pip" 2>/dev/null || true
  else
    err "Python não disponível"; exit 1
  fi
  # alias python3.12 -> python3 se necessário (install.sh usa python3.12)
  if [ "$PYCMD" != "python3.12" ] && ! command_exists python3.12; then
    warn "python3.12 não existe — criando atalho para $PYCMD (o install.sh usa 'python3.12')"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$(command -v "$PYCMD")" "$HOME/.local/bin/python3.12"
    export PATH="$HOME/.local/bin:$PATH"
  fi

  # Node.js 18+ / npm
  if ! command_exists node || [ "$(node -e 'process.stdout.write(String(Number(process.version.slice(1).split(".")[0])>=18))' 2>/dev/null)" != "true" ]; then
    warn "Node.js 18+ ausente — instalando via nvm"
    if command_exists curl || command_exists wget; then
      export NVM_DIR="$HOME/.nvm"
      if [ ! -s "$NVM_DIR/nvm.sh" ]; then
        if command_exists curl; then
          curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash >/dev/null 2>&1
        else
          wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash >/dev/null 2>&1
        fi
      fi
      [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm install 22 >/dev/null 2>&1 && ok "Node instalado via nvm ($(node --version))"
      # expor nvm ao shell atual
      . "$NVM_DIR/nvm.sh" 2>/dev/null && nvm use default >/dev/null 2>&1 || true
    else
      install_pkgs "nodejs npm" && ok "Node instalado via pacote"
    fi
  else
    ok "Node.js presente ($(node --version))"
  fi
  [ -n "${NVM_DIR:-}" ] && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" 2>/dev/null

  # pip
  if ! command_exists pip3 && ! $PYCMD -m pip --version &>/dev/null; then
    install_pkgs "python3-pip" || true
  fi

  # Bibliotecas de imagem/TTS/OCR (Linux)
  if [ "$PLATFORM" = "linux" ]; then
    install_pkgs "tesseract-ocr tesseract-ocr-por libgl1 libglib2.0-0 libsm6 libxext6 ffmpeg" 2>/dev/null \
      && ok "Bibliotecas de sistema instaladas" || warn "Algumas libs de sistema não instaladas"
  fi

  # Ollama
  if [ "$INSTALL_OLLAMA" = "yes" ] && ! command_exists ollama; then
    sec "Instalando Ollama (modelos locais)"
    if [ "$PLATFORM" = "macos" ] || command_exists curl; then
      if [ "$PLATFORM" = "linux" ] || [ "$PLATFORM" = "wsl" ]; then
        run_priv bash -c "curl -fsSL https://ollama.com/install.sh | sh" >/dev/null 2>&1 \
          && ok "Ollama instalado" || warn "Falha ao instalar Ollama (pode instalar depois manualmente)"
      else
        brew install ollama >/dev/null 2>&1 && ok "Ollama instalado via brew" || warn "Falha ao instalar Ollama"
      fi
    else
      warn "Sem curl — não foi possível instalar Ollama automaticamente"
    fi
  fi
fi

# ==============================================================
#  ETAPA 1 — Clonar o repositório
# ==============================================================
CURRENT_STEP="clonar repositório"
sec "Repositório ($REPO_URL → $INSTALL_DIR)"
if [ -d "$INSTALL_DIR/.git" ]; then
  ok "Repositório já existe — atualizando"
  ( cd "$INSTALL_DIR" && git pull origin "$BRANCH" >/dev/null 2>&1 && ok "Atualizado" || warn "Falha no git pull (seguindo mesmo assim)" )
else
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >/dev/null 2>&1 \
    && ok "Clonado com sucesso" || { err "Falha ao clonar de $REPO_URL (sem internet / repo não acessível?)"; exit 1; }
fi

cd "$INSTALL_DIR"

# ==============================================================
#  ETAPA 2 — Configurar .env (se não existir)
# ==============================================================
CURRENT_STEP="configurar .env"
sec "Variáveis de ambiente (.env)"
if [ ! -f "$INSTALL_DIR/backend/.env" ]; then
  if [ -f "$INSTALL_DIR/backend/.env.example" ]; then
    cp "$INSTALL_DIR/backend/.env.example" "$INSTALL_DIR/backend/.env"
    ok "backend/.env criado a partir do exemplo"
  elif [ -f "$INSTALL_DIR/.env.example" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/backend/.env"
    ok "backend/.env criado a partir do .env.example (raiz)"
  else
    warn "Nenhum .env.example encontrado — serão usados padrões do código"
  fi
else
  ok "backend/.env já existe"
fi

# ==============================================================
#  ETAPA 3 — Instalar dependências (via install.sh)
# ==============================================================
CURRENT_STEP="executar install.sh"
sec "Dependências (backend + frontend)"
if [ -f "$INSTALL_DIR/install.sh" ]; then
  chmod +x "$INSTALL_DIR/install.sh" "$INSTALL_DIR"/*.sh 2>/dev/null || true
  "$INSTALL_DIR/install.sh"
else
  warn "install.sh não encontrado no repo — instalando manualmente"
  cd "$INSTALL_DIR/backend"
  if [ ! -d .venv ]; then "${PYCMD:-python3.12}" -m venv .venv; fi
  .venv/bin/pip install --upgrade pip -q
  .venv/bin/pip install -r requirements.txt -q && ok "Backend instalado"
  cd "$INSTALL_DIR/frontend"
  npm install --silent && ok "Frontend instalado"
fi

# ==============================================================
#  ETAPA 4 — Modelos Ollama
# ==============================================================
CURRENT_STEP="baixar modelos Ollama"
if [ "$PULL_MODELS" = "yes" ] && command_exists ollama; then
  sec "Modelos de IA locais (Ollama)"
  if ! pgrep -x ollama &>/dev/null; then
    nohup ollama serve >/dev/null 2>&1 &
    warn "Ollama iniciado em segundo plano"
  fi
  for m in "${OLLAMA_MODELS[@]}"; do
    CURRENT_STEP="puxar modelo $m"
    if ! ollama list 2>/dev/null | grep -qi "${m%:*}"; then
      echo "  ↓ baixando $m (pode demorar)"
      ollama pull "$m" >/dev/null 2>&1 && ok "Modelo $m pronto" || warn "Falha ao puxar $m"
    else
      ok "Modelo $m já existe"
    fi
  done
fi

# ==============================================================
#  ETAPA 5 — Iniciar serviços
# ==============================================================
CURRENT_STEP="iniciar serviços"
if [ "$AUTO_START" = "yes" ]; then
  sec "Iniciando o StudyAgent"
  cd "$INSTALL_DIR"
  if [ -f start.sh ]; then
    chmod +x start.sh
    "$INSTALL_DIR/start.sh" || warn "start.sh terminou com avisos"
  else
    warn "start.sh não encontrado — inicie manualmente na pasta"
  fi

  # Aguardar API
  echo "  aguardando API ($API_URL)..."
  API_OK=0
  for _ in $(seq 1 40); do
    if curl -sf "$API_URL/api/health" >/dev/null 2>&1; then API_OK=1; break; fi
    sleep 1
  done
  [ "$API_OK" = "1" ] && ok "API respondeu em $API_URL" || warn "API ainda não respondeu (verifique o log/doctor.sh)"
fi

# ==============================================================
#  ETAPA 6 — Finalizar
# ==============================================================
sec "Conclusão"
echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║    StudyAgent instalado com sucesso!        ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║   Web:   $WEB_URL"
echo "  ║   API:   $API_URL"
echo "  ║   Pasta: $INSTALL_DIR"
echo "  ╚══════════════════════════════════════════════╝"
echo
echo "  Comandos úteis (na pasta $INSTALL_DIR):"
echo "    ./start.sh     → inicia os serviços"
echo "    ./stop.sh      → para os serviços"
echo "    ./doctor.sh    → verifica a saúde do sistema"
echo "    ./update.sh    → atualiza do GitHub"
echo
echo "  Log completo deste setup: $LOG_FILE"
echo

if [ "$OPEN_BROWSER" = "yes" ] && [ "$AUTO_START" = "yes" ]; then
  CURRENT_STEP="abrir navegador"
  sleep 2
  case "$PLATFORM" in
    wsl)    cmd.exe /c start "$WEB_URL" >/dev/null 2>&1 || true ;;
    macos)  open "$WEB_URL" 2>/dev/null || true ;;
    *)      ( xdg-open "$WEB_URL" >/dev/null 2>&1 || true ) & ;;
  esac
  ok "Abrindo navegador em $WEB_URL"
fi

# Executar health check se disponível
if [ -x "$INSTALL_DIR/doctor.sh" ]; then
  sec "Health Check (doctor.sh)"
  ( cd "$INSTALL_DIR" && "./doctor.sh" ) || true
fi

echo -e "${GREEN}Done!${NC}"
exit 0
