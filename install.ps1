# ============================================================
#  StudyAgent — INSTALADOR PARA WINDOWS NATIVO (PowerShell)
# ------------------------------------------------------------
#  Identifica o sistema operacional, baixa o projeto do GitHub
#  e instala/configura/incia o StudyAgent no Windows.
#
#  Como usar (PowerShell, clicar com botao direito -> "Executar
#  com PowerShell", ou abrir o PowerShell e colar):
#
#    powershell -ExecutionPolicy Bypass -File install.ps1
#
#  Ou direto do GitHub:
#    iex ((New-Object System.Net.WebClient).DownloadString(
#      'https://raw.githubusercontent.com/ANTONIOALGMAR/StudyAgent/main/install.ps1'))
# ============================================================

$ErrorActionPreference = "Stop"

# ── Configuração (edite se precisar) ──────────────────────────
$RepoUrl        = "https://github.com/ANTONIOALGMAR/StudyAgent.git"
$RepoZipUrl     = "https://github.com/ANTONIOALGMAR/StudyAgent/archive/refs/heads/main.zip"
$InstallDir     = Join-Path $env:USERPROFILE "StudyAgent"
$ApiUrl         = "http://localhost:8000"
$WebUrl         = "http://localhost:5173"
$OllamaModels   = @("llama3.1", "qwen2.5vl:7b", "nomic-embed-text")

function Write-Ok   { Write-Host "  [+] $args" -ForegroundColor Green }
function Write-Warn { Write-Host "  [!] $args" -ForegroundColor Yellow }
function Write-Err  { Write-Host "  [x] $args" -ForegroundColor Red }
function Write-Sec  { Write-Host ""; Write-Host "--- $args ---" -ForegroundColor Cyan }

# ── Detecção de plataforma ───────────────────────────────────
Write-Sec "Detectando sistema operacional"
$Platform = "windows"
# Se estiver dentro do WSL, o PowerShell nativo não roda — mas por segurança
# verificamos variáveis típicas de ambiente WSL.
if ($env:WSL_DISTRO_NAME) { $Platform = "wsl" }
Write-Ok "Plataforma: $Platform"

$PythonCmd = $null
foreach ($c in @("py", "python", "python3")) {
    try {
        $v = & $c --version 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $v -match "Python (\d+)\.(\d+)") {
            $major = $Matches[1]; $minor = $Matches[2]
            if ([int]$major -ge 3 -and [int]$minor -ge 10) {
                $PythonCmd = $c; break
            }
        }
    } catch {}
}
if (-not $PythonCmd) {
    Write-Err "Python 3.10+ não encontrado. Instale pelo Microsoft Store: https://www.python.org/downloads/"
    Write-Err "   e marque 'Add to PATH' durante a instalação."
    exit 1
}
Write-Ok "Python: $(& $PythonCmd --version)"

# ── Baixar o projeto ─────────────────────────────────────────
Write-Sec "Baixando o projeto do GitHub"
if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Ok "Pasta $InstallDir já existe — atualizando"
    Push-Location $InstallDir
    try { & git pull --ff-only origin main 2>$null } catch { Write-Warn "git pull falhou" }
    Pop-Location
} elseif (Test-Path $InstallDir) {
    Write-Warn "A pasta $InstallDir existe mas não é um repo git — usando como destino."
} else {
    $hasGit = Get-Command git -ErrorAction SilentlyContinue
    if ($hasGit) {
        Write-Ok "Git encontrado — clonando via git"
        New-Item -ItemType Directory -Force -Path (Split-Path $InstallDir) | Out-Null
        & git clone --depth 1 $RepoUrl $InstallDir
        if ($LASTEXITCODE -ne 0) { Write-Err "Falha no git clone"; exit 1 }
    } else {
        Write-Warn "Git não encontrado — baixando o ZIP do GitHub"
        $zip = Join-Path $env:TEMP "studyagent-main.zip"
        Invoke-WebRequest -Uri $RepoZipUrl -OutFile $zip
        $ex = Join-Path $env:TEMP "studyagent-extract"
        if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
        Expand-Archive -Path $zip -DestinationPath $ex -Force
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Copy-Item (Join-Path $ex "StudyAgent-main\*") $InstallDir -Recurse -Force
    }
    Write-Ok "Projeto baixado em $InstallDir"
}
Set-Location $InstallDir

# ── Backend ──────────────────────────────────────────────────
Write-Sec "Instalando backend (Python)"
$Backend = Join-Path $InstallDir "backend"
Set-Location $Backend

if (-not (Test-Path ".venv")) {
    & $PythonCmd -m venv .venv
    Write-Ok "Virtualenv criado"
}
$Pip = Join-Path $Backend ".venv\Scripts\pip.exe"
if (-not (Test-Path $Pip)) { $Pip = Join-Path $Backend ".venv\Scripts\pip3.exe" }
if (Test-Path (Join-Path $Backend ".env.example")) {
    if (-not (Test-Path (Join-Path $Backend ".env"))) {
        Copy-Item ".env.example" ".env"
        Write-Ok "backend/.env criado"
    }
}
& $Pip install --upgrade pip -q
& $Pip install -r requirements.txt -q
Write-Ok "Dependências do backend instaladas"

Write-Ok "Instalando insightface (reconhecimento facial — opcional)..."
try { & $Pip install insightface -q; Write-Ok "insightface instalado" }
catch { Write-Warn "insightface não instalado (reconhecimento facial indisponível). Não é obrigatório." }

# ── Frontend ─────────────────────────────────────────────────
Write-Sec "Instalando frontend (Node.js)"
$Frontend = Join-Path $InstallDir "frontend"
Set-Location $Frontend
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Err "npm não encontrado. Instale o Node.js 18+: https://nodejs.org/"
    Write-Err "   e reinicie o PowerShell."
    exit 1
}
npm install --silent
Write-Ok "Dependências do frontend instaladas"

# ── Tesseract OCR (para visão/documentos) ────────────────────
Write-Sec "Verificando Tesseract OCR (opcional)"
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
    Write-Warn "Tesseract OCR não encontrado. Bag visual/OCR de documentos ficará limitado."
    Write-Warn "Instale depois por: https://github.com/UB-Mannheim/tesseract/wiki"
}

# ── Ollama (modelos locais) ──────────────────────────────────
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Sec "Modelos locais (Ollama)"
    foreach ($m in $OllamaModels) {
        $present = & ollama list 2>$null | Select-String -SimpleMatch $m
        if (-not $present) {
            Write-Host "  ↓ baixando $m (pode demorar)"
            & ollama pull $m 2>$null | Out-Null
            Write-Ok "Modelo $m pronto"
        } else {
            Write-Ok "Modelo $m já existe"
        }
    }
} else {
    Write-Warn "Ollama não encontrado — instale: https://ollama.com/download/windows"
    Write-Warn "   Depois rode: ollama pull llama3.1; ollama pull qwen2.5vl:7b; ollama pull nomic-embed-text"
}

# ── Iniciar serviços ─────────────────────────────────────────
Write-Sec "Iniciando o StudyAgent"
function Start-Backend {
    $py = Join-Path $Backend ".venv\Scripts\python.exe"
    Set-Location $Backend
    Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" -WindowStyle Hidden
    Set-Location $Frontend
}
function Start-Frontend {
    Set-Location $Frontend
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev -- --port 5173" -WindowStyle Hidden
}

$apiUp = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue -InformationLevel Quiet
$webUp = Test-NetConnection -ComputerName localhost -Port 5173 -WarningAction SilentlyContinue -InformationLevel Quiet
if (-not $apiUp) { Start-Backend }
if (-not $webUp) { Start-Frontend }
Write-Ok "Serviços iniciados (backend 8000, frontend 5173)"

Start-Sleep -Seconds 6
$webUp = Test-NetConnection -ComputerName localhost -Port 5173 -WarningAction SilentlyContinue -InformationLevel Quiet
Start-Process $WebUrl

# ── Conclusão ────────────────────────────────────────────────
Write-Sec "Conclusão"
Write-Host ""
Write-Host "  ############################################"
Write-Host "  #   StudyAgent instalado com sucesso!      #"
Write-Host "  ############################################"
Write-Host "  Web:   $WebUrl"
Write-Host "  API:   $ApiUrl"
Write-Host "  Pasta: $InstallDir"
Write-Host ""
Write-Host "  Para reiniciar depois, entre na pasta e rode."
Write-Host "  backend:  cd $Backend; .venv\Scripts\uvicorn app.main:app --port 8000"
Write-Host "  frontend: cd $Frontend; npm run dev"
Write-Host ""
Write-Host "  Observação: o SO detectado foi: $Platform"
Write-Host "  (se veio 'wsl', prefira usar o setup.sh dentro do WSL.)"
Write-Host ""
exit 0
