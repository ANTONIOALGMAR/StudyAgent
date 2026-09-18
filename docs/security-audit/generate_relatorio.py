# -*- coding: utf-8 -*-
"""Gerador do Relatório de Auditoria de Segurança — StudyAgent.

Layout futurista: tema escuro com acentos neon (ciano/violeta/menta), cards com
barra de acento, gráficos escuros coerentes com a paleta e tipografia Ubuntu.
Glifos especiais (→, ◆, ●, ⚠, ▶, ▸) são renderizados via DejaVuSans (fallback).

Uso (ambiente isolado):
    .venv/bin/python generate_relatorio.py

Dependências: reportlab, matplotlib (instaladas no venv local).
Saída: docs/security-audit/relatorio-auditoria-seguranca.pdf
Imagens dos gráficos: charts/*.png (geradas e embutidas).
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape as _esc

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Caminhos ───────────────────────────────────────────────────────────────────
AUDIT_DIR = Path(__file__).resolve().parent
CHARTS_DIR = AUDIT_DIR / "charts"
OUT_PDF = AUDIT_DIR / "relatorio-auditoria-seguranca.pdf"
CHARTS_DIR.mkdir(exist_ok=True)

# ── Paleta (futurista / dark) ─────────────────────────────────────────────────
BG = "#05070F"
PANEL = "#0B1220"
PANEL2 = "#0F1830"
LINHA = "#1E293B"
TX = "#E2E8F0"
TX_FORTE = "#F8FAFC"
TX_NEUTRO = "#94A3B8"
CIANO = "#22D3EE"
VIOLETA = "#8B5CF6"
ROSA = "#F472B6"
MENTA = "#34D399"

COL = {
    "critica": colors.HexColor("#DC2626"),
    "alta": colors.HexColor("#F97316"),
    "media": colors.HexColor("#F59E0B"),
    "baixa": colors.HexColor("#3B82F6"),
    "info": colors.HexColor("#64748B"),
    "forte": colors.HexColor("#10B981"),
    "fundo": colors.HexColor(PANEL),
    "fundo2": colors.HexColor(PANEL2),
    "cinza": colors.HexColor(TX_NEUTRO),
    "cinza_claro": colors.HexColor(TX),
    "branco": colors.white,
    "preto": colors.HexColor(BG),
    "ciano": colors.HexColor(CIANO),
    "violeta": colors.HexColor(VIOLETA),
    "rosa": colors.HexColor(ROSA),
    "menta": colors.HexColor(MENTA),
}

HEX_SEV = {
    "critica": "#DC2626",
    "alta": "#F97316",
    "media": "#F59E0B",
    "baixa": "#3B82F6",
    "info": "#64748B",
    "forte": "#10B981",
}

PDFMETRICS = {
    "critica": "Crítica",
    "alta": "Alta",
    "media": "Média",
    "baixa": "Baixa",
    "info": "Informativa",
    "forte": "Ponto forte",
}

CONTAGENS_SEVERIDADE = {
    "critica": 0,
    "alta": 3,
    "media": 2,
    "baixa": 2,
    "info": 2,
}

CONTAGENS_CATEGORIA = {
    "C1 — Banco sem trava (isolamento)": 1,
    "C2 — Permissão definida no navegador": 3,
    "C3 — IDOR": 0,
    "C4 — Chaves expostas": 2,
    "C5 — Inputs sem tratamento (XSS)": 3,
}

ORDEM_SEV = ["critica", "alta", "media", "baixa", "info"]

# ── Fontes ─────────────────────────────────────────────────────────────────────
_FDIR = Path("/usr/share/fonts/truetype")


def _registrar_fontes() -> None:
    base = _FDIR / "ubuntu"
    pdfmetrics.registerFont(TTFont("Ubuntu", str(base / "Ubuntu-R.ttf")))
    pdfmetrics.registerFont(TTFont("Ubuntu-Bold", str(base / "Ubuntu-B.ttf")))
    pdfmetrics.registerFont(TTFont("Ubuntu-Italic", str(base / "Ubuntu-RI.ttf")))
    pdfmetrics.registerFont(TTFont("Ubuntu-BoldItalic", str(base / "Ubuntu-BI.ttf")))
    pdfmetrics.registerFont(TTFont("Ubuntu-Light", str(base / "Ubuntu-L.ttf")))
    pdfmetrics.registerFont(TTFont("Ubuntu-Medium", str(base / "Ubuntu-M.ttf")))
    pdfmetrics.registerFont(TTFont("Ubuntu-Cond", str(base / "Ubuntu-C.ttf")))
    pdfmetrics.registerFont(TTFont("UbuntuMono", str(base / "UbuntuMono-R.ttf")))
    pdfmetrics.registerFont(TTFont("UbuntuMono-Bold", str(base / "UbuntuMono-B.ttf")))
    reg_fam = dict(
        normal="Ubuntu",
        bold="Ubuntu-Bold",
        italic="Ubuntu-Italic",
        boldItalic="Ubuntu-BoldItalic",
    )
    registerFontFamily("Ubuntu", **reg_fam)
    registerFontFamily("UbuntuMono", normal="UbuntuMono", bold="UbuntuMono-Bold")
    djvu = _FDIR / "dejavu"
    pdfmetrics.registerFont(TTFont("DJV", str(djvu / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DJV-Bold", str(djvu / "DejaVuSans-Bold.ttf")))


def D(x: str, color: str | None = None) -> str:
    """Glifo via DejaVuSans (garante → ◆ ● ▶ ▸ ⚠ ✓ independente da fonte do tema)."""
    at = f' color="{color}"' if color else ""
    return f'<font name="DJV"{at}>{x}</font>'


_GLYPH_DEJA = set("→⇒◆●▶▸⚠✓")


def _djv(s: str) -> str:
    """Envolve glifos não cobertos por Ubuntu/UbuntuMono em DejaVu (após escape)."""
    for g in "→⇒◆●▶▸⚠✓":
        if g in s:
            s = s.replace(g, f'<font name="DJV">{g}</font>')
    return s


def _P(s: str) -> str:
    """Escape XML + fallback de glifos para conteúdo com dados do usuário."""
    if s is None:
        return ""
    return _djv(_esc(s))

def _hex(c: str):
    return colors.HexColor(c)


# ── Achados ────────────────────────────────────────────────────────────────────
ACHADOS = [
    {
        "id": "A1",
        "categoria": "C1",
        "severidade": "alta",
        "ref": "backend/app/main.py:31,68-77 · routers",
        "titulo": "API sem autenticação expõe todos os dados pessoais e ações",
        "descricao": (
            "Nenhuma dependência de autenticação é aplicada em main.py e a maioria dos "
            "handlers de rota não exige PIN. Qualquer requisição HTTP — de um processo "
            "local, página web maliciosa na mesma máquina, ou da rede caso a porta seja "
            "publicada — lê/grava documentos, conversas, perfil, faces e estatísticas. "
            "Equivalente adaptado de 'banco sem trava' num app single-user: não existe "
            "controle de quem acessa os dados."
        ),
        "evidencia": (
            "main.py:31 `app = FastAPI(...)`; routers incluídos sem dependency (linhas 70-77); "
            "ex.: documents.py:53 `@router.get('/documents/{doc_id}/file')` serve o arquivo sem "
            "checar permissão nem credencial; chat.py:68-75 `/sessions` e "
            "`/sessions/{id}/messages` devolvem histórico; tutor.py:193 `/profile`; "
            "facial.py:92 `/face/list`."
        ),
        "porque": (
            "A única proteção do projeto é o PIN em 3 rotas de ativação de permissão. "
            "Dados pessoais (documentos anexados, conversas, biometria facial, perfil) "
            "ficam acessíveis a qualquer chamada sem credencial. O Dockerfile:30 sobe "
            "uvicorn com `--host 0.0.0.0`; o compose faz bind em 127.0.0.1 (por padrão), "
            "mas um deploy com porta publicada expõe tudo à LAN."
        ),
        "impacto": "Exfiltração de dados pessoais; manipulação do estado da aplicação sem autorização.",
        "correcao": (
            "Adicionar camada de auth local (ex.: token bearer/PIN convertido em sessão "
            "httpOnly, ou header fixo trocado por login) aplicada globalmente via "
            "dependency no app; manter bind 127.0.0.1; nunca publicar a porta sem auth."
        ),
        "aceite": [
            "Todos os endpoints /api/* exigem um token/sessão válidos (teste automatizado).",
            "Falha de auth → 401 e log.",
            "Dockerfile/compose não publicam a API na rede sem auth.",
        ],
    },
    {
        "id": "A2",
        "categoria": "C2",
        "severidade": "alta",
        "ref": "backend/app/routers/tutor.py:288-303",
        "titulo": "Aprovação de automação dispensa PIN local (confirmação só no navegador)",
        "descricao": (
            "`POST /api/actions/{proposal_id}/approve` e `/reject` executam sem `require_pin`. "
            "O docstring de local_auth.py:6-7 afirma que aprovar/rejeitar propostas de automação "
            "DEVE exigir PIN. O frontend ActionConfirm.tsx:49-54 exibe o botão '✓ executar' "
            "sem pedir PIN — o 'gate' é apenas a UI."
        ),
        "evidencia": (
            "tutor.py:288-294 `@router.post('/actions/{proposal_id}/approve') ... return "
            "automation.approve(proposal_id)` — sem require_pin; tutor.py:297-303 idem para "
            "reject. automation.py:55-73 approva e executa a proposta. ActionConfirm.tsx:49-54 "
            "mostra os botões de confirmação sem exigir PIN."
        ),
        "porque": (
            "O modelo documentado ('PIN garante consentimento') é viável apenas se o servidor "
            "validar o privilégio em toda via de concessão. Aqui a ação é grampeável por um "
            "request simples (POST sem body → sem preflight CORS), permitindo a uma página "
            "local maliciosa aprovar propostas (open_url/web_search) sem interação."
        ),
        "impacto": "Execução de ações propostas pelo agente sem consentimento do usuário (CSRF local + falha de autorização).",
        "correcao": (
            "Exigir `require_pin` em approve/reject (e propor CSRF token/check de header "
            "customizado para requests simples). Manter alinhado ao docstring de local_auth."
        ),
        "aceite": [
            "require_pin presente em approve e reject.",
            "Teste de API ativa sem PIN → 401.",
            "Frontend solicita o PIN antes de aprovar/rejeitar.",
        ],
    },
    {
        "id": "A3",
        "categoria": "C2",
        "severidade": "media",
        "ref": "backend/app/routers/documents.py:53-72",
        "titulo": "Download de documento ignora a permissão file_access",
        "descricao": (
            "`GET /api/documents/{doc_id}/file` não chama `permissions.require('file_access')`, "
            "enquanto os endpoints irmãos audio/plan (documents.py:92-94) e audio (documents.py:105-107) "
            "exigem. Desativar 'file_access' na UI não impede o download do documento."
        ),
        "evidencia": "documents.py:57-72 (handler sem checagem) vs documents.py:92,105 (`permissions.require('file_access')`).",
        "porque": "Inconsistência de autorização: o gate exibido no navegador (painel de permissões) não corresponde à proteção do servidor nesta rota de leitura de conteúdo.",
        "impacto": "Conteúdo do documento legível mesmo com a permissão de acesso a arquivos revogada.",
        "correcao": "Adicionar `permissions.require('file_access')` no início do handler document_file (ou mover para um helper comum com os demais).",
        "aceite": [
            "Com file_access=false, GET /documents/{id}/file → 403.",
            "Teste cobre as 3 rotas de documento de forma consistente.",
        ],
    },
    {
        "id": "A4",
        "categoria": "C2",
        "severidade": "info",
        "ref": "backend/app/routers/tutor.py:396-431",
        "titulo": "PIN é gate de ativação única, não revalidado no uso",
        "descricao": (
            "O PIN (require_pin) é exigido apenas no momento de ATIVAR uma permissão perigosa. "
            "Uma vez ativa, nenhum uso da capability revalida o PIN. Hoje nenhuma ferramenta "
            "usa command_execution/mouse_control/keyboard_control (nenhuma registrada em "
            "registered_tools.py), então o impacto atual é baixo, mas a arquitetura herdaria o "
            "risco de qualquer ferramenta futura."
        ),
        "evidencia": "tutor.py:399-400 `if body.value and name in DANGEROUS_PERMISSIONS: require_pin(request)`; registros em registered_tools.py usam apenas 'internet' e 'filesystem'.",
        "porque": "Modelo presume que a ativação é o momento de consentimento; um único request de ativação (com PIN vazado/observado) deixa o recurso disponível sem novo desafio.",
        "impacto": "Baixo hoje; médio se for adicionada ferramenta de execução regida só pela permissão ativada.",
        "correcao": "Para capabilities críticas (command_execution), revalidar o PIN no uso (ou exigir timeout de reconsentimento). Documentar o modelo.",
        "aceite": [
            "Ferramenta crítica nova revalida PIN ou possui timeout de consentimento.",
            "README descreve o modelo de reconsentimento.",
        ],
    },
    {
        "id": "A5",
        "categoria": "C4",
        "severidade": "media",
        "ref": "backend/.env:4",
        "titulo": "PIN de autenticação em claro no working tree",
        "descricao": (
            "`STUDYAGENT_PIN=c59dc128b5626deba268410a` existe no arquivo backend/.env do "
            "diretório de trabalho. O arquivo é gitignored (não rastreado) e o valor não está no "
            "histórico do git — verificado —, mas o segredo trafega em claro no disco e pode "
            "vazar via `git add -f`, backup/manual ou tar/zip recursivo da pasta."
        ),
        "evidencia": "backend/.env:4 `STUDYAGENT_PIN=c59dc128b5626deba268410a`; .gitignore:17 `backend/.env`; risk-register.md:18 (R4) já documenta o risco.",
        "porque": "Qualquer segredo em claro no disco aumenta a superfície (malware local lê o arquivo). O próprio risk-register reconhece R4 como risco residual.",
        "impacto": "Comprometimento do PIN de consentimento se o arquivo vazar (backup/commit incladvertido).",
        "correcao": "Rotacionar o PIN; injetar via environment variables do deploy/service; garantir que backup.sh nunca inclua .env; adicionar guard em script de backup/empacotamento.",
        "aceite": [
            "PIN rotacionado e nova variante fora do working tree rastreável.",
            "backup.sh e scripts de empacotamento excluem .env (teste).",
            "Grep de segredo conhecido retorna 0 em artefatos de entrega.",
        ],
    },
    {
        "id": "A6",
        "categoria": "C4",
        "severidade": "baixa",
        "ref": "backend/app/core/env_validation.py · docker-compose.yml:12-15",
        "titulo": "Sem validação de startup nem injeção de STUDYGAGENT_PIN no container",
        "descricao": (
            "`validate_environment()` não valida presença/fortaleza de STUDYAGENT_PIN. O "
            ".env.example deixa o valor vazio por padrão (fail-closed correto para as operações "
            "perigosas, que retornam 401), mas o docker-compose não injeta a variável — no "
            "container todas as operações privilegiadas ficam permanentemente 401 (recurso "
            "inerte) sem nenhum aviso claro."
        ),
        "evidencia": "env_validation.py:79-92 (checks de python/tesseract/ollama/disco/dirs, sem PIN); docker-compose.yml:12-15 (environment sem STUDYAGENT_PIN).",
        "porque": "Padrão vazio é seguro por omissão, mas a falta de verificação de startup permite deploy silenciosamente sem a capacidade esperada e sem alerta.",
        "impacto": "Baixo (disponibilidade/observabilidade); sem vazamento, mas configuração ambígua.",
        "correcao": "Avisar em validate_environment() quando STUDYAGENT_PIN estiver ausente em modo não-interativo; injetar a variável no compose a partir do ambiente do host.",
        "aceite": [
            "Log de aviso/warning no startup quando PIN ausente.",
            "Compose injeta STUDYAGENT_PIN (ou bloquear modo sem PIN).",
        ],
    },
    {
        "id": "A7",
        "categoria": "C5",
        "severidade": "alta",
        "ref": "backend/app/tools/web_search.py:200-212",
        "titulo": "SSRF via web_search/open_url com permissão internet habilitada por padrão",
        "descricao": (
            "`fetch_page` valida apenas o prefixo `^https?://` (web_search.py:202) e executa "
            "`requests.get(url)` seguindo redirecionamentos (linha 204), sem vetar endereços "
            "privados/link-local/metadata (127.0.0.0/8, 169.254.169.254, 10/8, 172.16/12, "
            "192.168/16, ::1). A ferramenta open_url (registered_tools.py:79-80) e o próprio "
            "web_search_tool, que baixa cada resultado (registered_tools.py:43), usam esse "
            "código. A permissão que as gateia (internet) está ATIVA por padrão "
            "(permissions.py:28, config/permissions.json:6) sem exigir PIN."
        ),
        "evidencia": (
            "web_search.py:200-212; registered_tools.py:37-58 (web_search_tool) e 79-80 "
            "(open_url_tool); permissions.py:28 `'internet': True`."
        ),
        "porque": (
            "Gatilhos: (1) prompt injection — conteúdo de página web ou do próprio chat instrui "
            "o LLM a chamar open_url com URL interna; (2) o modelo escolhe URLs de resultados; "
            "(3) o usuário pede abertura de URL. O texto baixado volta para a resposta do chat "
            "(exfiltração de serviços internos/metadados)."
        ),
        "impacto": "Acesso e exfiltração de endpoints internos (Ollama, API local, metadados de cloud para o Llama/host se hospedado).",
        "correcao": (
            "Permitir apenas destinos públicos: resolver DNS e bloquear IPs privados/link-local/"
            "metadata; não seguir redirects (allow_redirects=False) reavaliando cada destino; "
            "por default `internet` = False (opt-in com PIN)."
        ),
        "aceite": [
            "Teste: open_url para 127.0.0.1/169.254.169.254/10.x → erro.",
            "Redirect para IP privado → bloqueado.",
            "internet default = false (e 401/403 sem PIN).",
        ],
    },
    {
        "id": "A8",
        "categoria": "C5",
        "severidade": "baixa",
        "ref": "frontend/nginx.conf:1-15",
        "titulo": "Sem security headers (CSP, X-Content-Type-Options, X-Frame-Options) no nginx",
        "descricao": "A configuração de servição do frontend não envia Content-Security-Policy nem demais headers de endurecimento. Defesa em profundidade ausente.",
        "evidencia": "frontend/nginx.conf:1-15 (apenas listen/root/try_files/proxy_pass).",
        "porque": "Sem CSP, qualquer futuro vetor XSS (ou script vindo do futuro renderizador de markdown) teria caminho livre para exfiltração do PIN em sessionStorage.",
        "impacto": "Baixo hoje (sem XSS encontrado), mitigação faltante.",
        "correcao": "Adicionar headers no bloco server (CSP default-src 'self'; X-Content-Type-Options: nosniff; X-Frame-Options: DENY; Referrer-Policy).",
        "aceite": [
            "curl retorna os headers.",
            "CSP não quebra assets do bundle existente.",
        ],
    },
    {
        "id": "A9",
        "categoria": "C5",
        "severidade": "info",
        "ref": "backend/app/routers/tutor.py:464-482",
        "titulo": "Decorator de rota aplicado a classe; funções não registradas (código morto)",
        "descricao": (
            "`@router.post('/errors/review-topic')` decora uma classe (ReviewTopicRequest) e "
            "`review_topic_errors`/`generate_flashcards_from_errors` não possuem decorator — "
            "não expõem rotas como previsto. Sem impacto de segurança direto, mas rotas que "
            "parecem ativas não existem e qualquer handler futuro copiado deste padrão pode "
            "escapar do controle."
        ),
        "evidencia": "tutor.py:464-466 (`@router.post('/errors/review-topic')` sobre class ...) e 475-482 (decorator sobre class; funções sem decorator).",
        "porque": "Padrão frágil que mascara a superfície real de exposição da API; indicador de revisão.",
        "impacto": "Informativo (funcional); superfície esperada não condiz com a real.",
        "correcao": "Mover os decorators para as funções; remover/reexpor conforme intenção; adicionar teste de rota.",
        "aceite": [
            "Routes /errors/review-topic e /flashcards/generate-from-errors respondem conforme documentado (ou são removidas).",
            "Teste de rota cobre o endpoint.",
        ],
    },
]

PONTOS_FORTES = [
    ("SQL totalmente parametrizado", "memory.py, tutor/*.py e export_import.py usam apenas placeholders '?' — nenhuma concatenação de SQL no código (varredura por execute(f…/.format retornou 0)."),
    ("Calculadora AST-safe", "calculator.py:17-33 avalia apenas árvore AST com allowlist de operações — sem eval de texto do usuário."),
    ("CSV export com mitigação de fórmula", "export_import.py:20-28 prefixa ' em valores iniciados por =,+,-,@,\t,\r (CSV injection)."),
    ("Sem XSS clássico no frontend", "nenhum dangerouslySetInnerHTML/innerHTML/v-html/eval/new Function em frontend/src; chat é renderizado como texto React (ChatMessages.tsx:23)."),
    ("CORS restrito", "main.py:61-66 permite apenas localhost:5173 e 127.0.0.1:5173."),
    ("Rate limiting", "slowapi em /chat, /exercises/*, /flashcards/generate, /study-plans/generate, /audio/*, /actions, /face/* (ex.: chat.py:38)."),
    ("PIN com comparação constante e fail-closed", "local_auth.py:36-46 usa hmac.compare_digest; sem config → 401 (mode deny)."),
    ("Ferramentas de arquivo negadas por padrão", "registered_tools.py exige permissão 'filesystem' inexistente nas permissões (permissions.py:23-32) → sempre bloqueadas (fail-closed)."),
    ("Upload restrito", "documents.py:35-37 valida extensão (.pdf/.txt/.md) e salva com nome UUID; PDF é validado/extraído antes de persistir."),
    ("Content-Disposition sanitizada", "documents.py:64 remove \\ ; \" CR LF do nome no header (sem header injection)."),
    ("Bind local por padrão", "systemd (scripts/*.service) usa --host 127.0.0.1; docker-compose publica 127.0.0.1:8000/5173."),
    ("Sem segredos no git/bundle", ".env gitignored; git log -S e bundle dist sem chaves/API keys (apenas hashes de integridade de package-lock)."),
    ("Permissões de sensores no backend", "microfone/câmera/tela exigem permissions.require (audio.py:30, facial.py:47/63/81/95/104, screen.py:44/86)."),
]

RECOMENDACOES = [
    ("P1", "Autenticação na API", "Aplicar dependency global de auth local (token/sessão httpOnly derivada do PIN) em todos os /api/*; nunca publicar a porta sem auth (A1)."),
    ("P1", "PIN em aprovação de automação", "require_pin em /actions/{id}/approve e /reject + CSRF/check de header customizado; alinhar ao docstring de local_auth (A2)."),
    ("P1", "Endurecer fetch de URLs", "Allowlist pública com bloqueio de IPs privados/link-local/metadata, sem seguir redirects, e internet default = False (opt-in com PIN) (A7)."),
    ("P2", "Consistência de file_access", "Exigir file_access em GET /documents/{id}/file (A3)."),
    ("P2", "Segredo do PIN", "Rotacionar o PIN; injetar via env do deploy/service; blindar backup/empacotamento contra inclusão de .env (A5)."),
    ("P2", "Validação de startup", "Avisar quando STUDYAGENT_PIN ausente; injetar a variável no compose (A6)."),
    ("P3", "Security headers", "CSP + X-Content-Type-Options + X-Frame-Options + Referrer-Policy no nginx (A8)."),
    ("P3", "Sanar rotas mortas", "Corrigir decorators de /errors/review-topic e /flashcards/generate-from-errors (A9)."),
    ("P3", "Modelo de reconsentimento", "Para capability crítica futura: revalidar PIN no uso/timeout; documentar (A4)."),
]

# ── Issues para GitHub ─────────────────────────────────────────────────────────
ISSUES = [
    {
        "titulo": "[Segurança] API do StudyAgent sem autenticação expõe dados pessoais e ações privilegiadas",
        "labels": "security, alta",
        "body": (
            "## Problema\n"
            "A API FastAPI (backend/app/main.py) não aplica nenhuma dependência de autenticação "
            "e, exceto por 3 rotas de ativação de permissão, nenhum handler valida credencial ou PIN. "
            "Endpoints como `GET /api/documents/{doc_id}/file`, `GET /api/sessions`, "
            "`GET /api/sessions/{session_id}/messages`, `GET /api/profile` e `GET /api/face/list` "
            "são legíveis por qualquer requisição.\n\n"
            "## Por que é explorável\n"
            "Um processo ou página local maliciosa (ou a rede, se a porta for publicada) lê todos os "
            "dados pessoais sem credencial. `Dockerfile:30` sobe uvicorn com `--host 0.0.0.0`.\n\n"
            "## Evidência\n"
            "`backend/app/main.py:31,70-77` (routers sem dependency) · `backend/app/routers/documents.py:53` "
            "· `backend/app/routers/chat.py:68-75` · `backend/app/routers/facial.py:92`.\n\n"
            "## Impacto\n"
            "Exfiltração de documentos/conversas/perfil/biometria; manipulação de estado sem autorização.\n\n"
            "## Sugestão de correção\n"
            "Adicionar token/sessão local (ex.: PIN convertido em cookie httpOnly ou header bearer) "
            "aplicado globalmente via dependency; manter bind 127.0.0.1; não publicar a porta sem auth.\n\n"
            "## Critérios de aceite\n"
            "- [ ] Todos os endpoints /api/* exigem autenticação (teste automatizado por rota).\n"
            "- [ ] Sem credencial → 401 + log.\n"
            "- [ ] Dockerfile/compose não expõem a API em 0.0.0.0 sem auth."
        ),
    },
    {
        "titulo": "[Segurança] Aprovação de automação dispensa PIN local — 'confirmação' só no navegador",
        "labels": "security, alta",
        "body": (
            "## Problema\n"
            "`POST /api/actions/{proposal_id}/approve` e `/reject` (backend/app/routers/tutor.py:288-303) "
            "não chamam `require_pin`, contrariando a especificação em `backend/app/security/local_auth.py:6-7`, "
            "que determina PIN para aprovar/rejeitar automação. O frontend exibe '✓ executar' sem exigir PIN "
            "(frontend/src/components/ActionConfirm.tsx:49-54).\n\n"
            "## Por que é explorável\n"
            "A 'confirmação' do usuário é apenas um clique na UI. O endpoint aceita POST simples sem body "
            "(sem preflight CORS), permitindo a uma página local maliciosa aprovar propostas "
            "(ex.: open_url/web_search) sem interação.\n\n"
            "## Evidência\n"
            "`backend/app/routers/tutor.py:288-294 e 297-303` · `backend/app/tutor/automation.py:55-73` · "
            "`frontend/src/components/ActionConfirm.tsx:49-54`.\n\n"
            "## Impacto\n"
            "Execução de ações do agente sem consentimento (CSRF local + falha de autorização).\n\n"
            "## Sugestão de correção\n"
            "Exigir `require_pin` em approve/reject; adicionar check de header customizado/CSRF token "
            "para requests simples; pedir PIN na UI antes de confirmar.\n\n"
            "## Critérios de aceite\n"
            "- [ ] require_pin presente em approve e reject.\n"
            "- [ ] Chamada sem PIN → 401 (teste).\n"
            "- [ ] Frontend solicita PIN antes de aprovar/rejeitar."
        ),
    },
    {
        "titulo": "[Segurança] SSRF via web_search/open_url com permissão internet habilitada por padrão",
        "labels": "security, alta",
        "body": (
            "## Problema\n"
            "`fetch_page` (backend/app/tools/web_search.py:200-212) valida apenas o prefixo `https?://` "
            "e chama `requests.get(url)` seguindo redirects, permitindo destinos internos "
            "(127.0.0.1, 10.x, 172.16/12, 192.168.x, 169.254.169.254, ::1). As ferramentas `open_url` "
            "(registered_tools.py:79-80) e `web_search` (registered_tools.py:43, que baixa cada "
            "resultado) usam esse fluxo; `internet` está ativa por padrão (permissions.py:28) e não "
            "exige PIN para desativar/ativar.\n\n"
            "## Por que é explorável\n"
            "Gatilhos: prompt injection (conteúdo web/chat instrui o LLM a abrir URL interna), o agente "
            "escolhendo URLs de resultados, ou o usuário pedindo abertura de URL. O conteúdo baixado "
            "volta na resposta do chat (exfiltração).\n\n"
            "## Evidência\n"
            "`backend/app/tools/web_search.py:200-212` · `backend/app/core/registered_tools.py:37-58,79-80` "
            "· `backend/app/security/permissions.py:28` · `config/permissions.json:6`.\n\n"
            "## Impacto\n"
            "Leitura/exfiltração de endpoints internos (Ollama, API local, metadados de cloud).\n\n"
            "## Sugestão de correção\n"
            "Bloquear IPs privados/link-local/metadata após resolução DNS; `allow_redirects=False` "
            "reavaliando cada destino; `internet` por padrão = false com opt-in via PIN.\n\n"
            "## Critérios de aceite\n"
            "- [ ] open_url/web_search para 127.0.0.1, 169.254.169.254, 10.x → erro.\n"
            "- [ ] Redirect para IP privado → bloqueado.\n"
            "- [ ] Default de 'internet' = false; ativação exige PIN."
        ),
    },
    {
        "titulo": "[Segurança] Download de documento ignora a permissão file_access",
        "labels": "security, media",
        "body": (
            "## Problema\n"
            "`GET /api/documents/{doc_id}/file` (backend/app/routers/documents.py:53-72) não chama "
            "`permissions.require('file_access')`, ao contrário dos irmãos `/audio/plan` (linha 92) "
            "e `/audio` (linha 105).\n\n"
            "## Por que é explorável\n"
            "O painel de permissões do navegador comunica 'file_access' como controle, mas a rota de "
            "leitura de conteúdo não aplica o mesmo controle no servidor.\n\n"
            "## Evidência\n"
            "`backend/app/routers/documents.py:53-72` vs `documents.py:92,105`.\n\n"
            "## Impacto\n"
            "Documento legível mesmo com file_access revogada.\n\n"
            "## Sugestão de correção\n"
            "Adicionar `permissions.require('file_access')` ao handler document_file (helper comum).\n\n"
            "## Critérios de aceite\n"
            "- [ ] file_access=false → GET /documents/{id}/file retorna 403.\n"
            "- [ ] Teste cobre as 3 rotas de documento."
        ),
    },
    {
        "titulo": "[Segurança] PIN de autenticação em claro no working tree (backend/.env)",
        "labels": "security, media",
        "body": (
            "## Problema\n"
            "`backend/.env:4` contém `STUDYAGENT_PIN=c59dc128b5626deba268410a`. O arquivo é "
            "gitignored e não consta do histórico (verificado), mas o segredo fica em claro no disco.\n\n"
            "## Por que é explorável\n"
            "Vazamento por `git add -f`, backup/manual ou tar/zip recursivo da pasta expõe o "
            "consentimento. O risk-register já marca R4 como risco residual.\n\n"
            "## Evidência\n"
            "`backend/.env:4` · `.gitignore:17` · `risk-register.md:18`.\n\n"
            "## Impacto\n"
            "Comprometimento do PIN de consentimento se o arquivo vazar.\n\n"
            "## Sugestão de correção\n"
            "Rotacionar o PIN; injetar via variáveis de ambiente do deploy; blindar backup/"
            "empacotamento contra inclusão de .env.\n\n"
            "## Critérios de aceite\n"
            "- [ ] PIN rotacionado e variante antiga não rastreável.\n"
            "- [ ] backup.sh e empacotamento excluem .env (teste).\n"
            "- [ ] Grep do segredo conhecido retorna 0 nos artefatos."
        ),
    },
    {
        "titulo": "[Segurança] Hardening complementar: validação de PIN no startup, reconsentimento e security headers",
        "labels": "security, baixa",
        "body": (
            "## Problema\n"
            "Três itens menores reunidos:\n"
            "1. `validate_environment()` (backend/app/core/env_validation.py:79-92) não avisa quando "
            "STUDYAGENT_PIN está ausente; o compose não injeta a variável (docker-compose.yml:12-15), "
            "deixando o container com operações privilegiadas permanentemente 401 sem alerta (A6).\n"
            "2. O PIN é gate de ATIVAÇÃO única; o uso da capability não revalida (tutor.py:399-400). "
            "Impacto atual baixo (nenhuma ferramenta usa command_execution hoje), mas arriscado para "
            "ferramentas futuras (A4).\n"
            "3. frontend/nginx.conf não envia CSP nem X-Content-Type-Options/X-Frame-Options (A8).\n\n"
            "## Sugestão de correção\n"
            "- Avistar/alertar quando PIN ausente; injetar a variável no compose.\n"
            "- Revalidar PIN (ou timeout de reconsentimento) em capability crítica; documentar o modelo.\n"
            "- Adicionar headers de segurança (CSP default-src 'self', nosniff, DENY, Referrer-Policy).\n\n"
            "## Critérios de aceite\n"
            "- [ ] Aviso de PIN ausente no startup.\n"
            "- [ ] Compose injeta STUDYAGENT_PIN.\n"
            "- [ ] Documentação do modelo de reconsentimento.\n"
            "- [ ] Headers CSP/nosniff/X-Frame presentes (curl)."
        ),
    },
]

# ── Rodapé/cabeçalho ───────────────────────────────────────────────────────────
RELATORIO_NOME = "Relatório de Auditoria de Segurança — StudyAgent"
DATA_AUDITORIA = "02 de setembro de 2026"
TOTAL = None  # definido em main() após a primeira passada

# ── Estilos ────────────────────────────────────────────────────────────────────
def _st(name, **kw):
    return ParagraphStyle(name, **kw)


BADGE = ParagraphStyle(
    "badge", fontName="UbuntuMono", fontSize=7.5, leading=10,
    textColor=colors.HexColor(CIANO), spaceAfter=6,
)

TITULO = ParagraphStyle(
    "titulo", fontName="Ubuntu-Light", fontSize=31, leading=35,
    textColor=colors.HexColor(TX_FORTE),
)

SUB = ParagraphStyle(
    "sub", fontName="Ubuntu-Medium", fontSize=13, leading=18,
    textColor=colors.HexColor(TX_FORTE), spaceBefore=4,
)

META = ParagraphStyle(
    "meta", fontName="Ubuntu", fontSize=9, leading=13,
    textColor=colors.HexColor(TX_NEUTRO),
)

SECTION = ParagraphStyle(
    "section", fontName="Ubuntu-Bold", fontSize=15.5, leading=20,
    textColor=colors.HexColor(TX_FORTE), spaceBefore=4,
)

H2 = ParagraphStyle(
    "h2", fontName="Ubuntu-Bold", fontSize=10, leading=14,
    textColor=colors.HexColor(CIANO),
)

BODY = ParagraphStyle(
    "body", fontName="Ubuntu", fontSize=9.2, leading=13.1,
    textColor=colors.HexColor(TX), alignment=TA_JUSTIFY,
)

BODY_C = ParagraphStyle(
    "bodyc", fontName="Ubuntu", fontSize=9.2, leading=13,
    textColor=colors.HexColor(TX), alignment=TA_CENTER,
)

MUTED = ParagraphStyle(
    "muted", fontName="Ubuntu-Italic", fontSize=8, leading=11,
    textColor=colors.HexColor(TX_NEUTRO),
)

CELLID = ParagraphStyle(
    "cellid", fontName="UbuntuMono-Bold", fontSize=8, leading=10,
    textColor=colors.HexColor(TX_FORTE),
)

ACHMETA = ParagraphStyle(
    "achmeta", fontName="UbuntuMono", fontSize=7.4, leading=10,
    textColor=colors.HexColor(TX_NEUTRO),
)

ACHTIL = ParagraphStyle(
    "achtul", fontName="Ubuntu-Bold", fontSize=10.4, leading=13.4,
    textColor=colors.HexColor(TX_FORTE),
)

CODES = ParagraphStyle(
    "codes", fontName="UbuntuMono", fontSize=7.6, leading=10.4,
    textColor=colors.HexColor("#C9D7E8"),
)

ISSH = ParagraphStyle(
    "issh", fontName="Ubuntu-Bold", fontSize=11, leading=14,
    textColor=colors.HexColor(TX_FORTE),
)


def _vgrad(canvas, x0, y0, x1, y1, c_top, c_bot, n=60):
    """Gradiente vertical via faixas horizontais (robusto em qualquer viewer)."""
    ct = colors.HexColor(c_top)
    cb = colors.HexColor(c_bot)
    for i in range(n):
        t = i / max(n - 1, 1)
        canvas.setFillColor(colors.Color(
            cb.red + (ct.red - cb.red) * t,
            cb.green + (ct.green - cb.green) * t,
            cb.blue + (ct.blue - cb.blue) * t,
        ))
        yy = y0 + (y1 - y0) * (i + 0.5) / n
        canvas.rect(x0, yy, x1 - x0, (y1 - y0) / n, stroke=0, fill=1)


def _fundo(canvas, _doc):
    """Furniture de todas as páginas: fundo, halos, grade de pontos, molduras, rodapé."""
    W, H = A4
    canvas.saveState()
    _vgrad(canvas, 0, 0, W, H, "#0A1626", BG)
    canvas.setFillColor(_hex("#0D1E33"))
    canvas.circle(W * 0.92, H * 0.88, 3.4 * cm, stroke=0, fill=1)
    canvas.setFillColor(_hex("#120F24"))
    canvas.circle(W * 0.06, H * 0.1, 3.8 * cm, stroke=0, fill=1)
    canvas.setFillColor(_hex("#0E1B2E"))
    for gx in range(30):
        for gy in range(6):
            canvas.circle(1.0 * cm + gx * 0.65 * cm, 0.9 * cm + gy * 0.8 * cm, 0.6, stroke=0, fill=1)
    canvas.setStrokeColor(_hex(LINHA))
    canvas.setLineWidth(0.6)
    canvas.line(2 * cm, H - 1.35 * cm, W - 2 * cm, H - 1.35 * cm)
    canvas.line(2 * cm, 1.35 * cm, W - 2 * cm, 1.35 * cm)
    canvas.setStrokeColor(_hex(CIANO))
    canvas.setLineWidth(1.6)
    canvas.line(2 * cm, H - 1.35 * cm, 4.2 * cm, H - 1.35 * cm)
    canvas.line(2 * cm, 1.35 * cm, 4.2 * cm, 1.35 * cm)
    canvas.setFillColor(_hex(TX_NEUTRO))
    canvas.setFont("Ubuntu", 7.2)
    canvas.drawString(2 * cm, 0.95 * cm, "SECURE. REVIEW. EVOLVE.")
    canvas.drawRightString(W - 2 * cm, 0.95 * cm, f"{_doc.page} · {TOTAL if TOTAL else 1}")
    canvas.setFillColor(_hex(CIANO))
    canvas.circle(2 * cm - 3.2, H - 1.35 * cm, 1.1, stroke=0, fill=1)
    canvas.restoreState()


def _capa(canvas, doc):
    """Camada extra da capa: geometria futurista (nós/hexágonos) no topo-direita."""
    W, H = A4
    _fundo(canvas, doc)
    canvas.saveState()
    import math
    cx, cy = W * 0.86, H - 2.4 * cm
    r = 2.15 * cm
    ang = [math.radians(i * 60 + 30) for i in range(6)]
    pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in ang]
    pts2 = [(cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a)) for a in ang]
    path = canvas.beginPath()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    path.close()
    canvas.setStrokeColor(_hex(CIANO))
    canvas.setLineWidth(1.3)
    canvas.drawPath(path, stroke=1, fill=0)
    canvas.setFillColor(_hex("#0F2036"))
    path2 = canvas.beginPath()
    path2.moveTo(*pts2[0])
    for p in pts2[1:]:
        path2.lineTo(*p)
    path2.close()
    canvas.drawPath(path2, stroke=0, fill=1)
    for i, p in enumerate(pts):
        canvas.setFillColor(_hex(VIOLETA if i % 2 else ROSA))
        canvas.circle(p[0], p[1], 1.9, stroke=0, fill=1)
    canvas.setFillColor(_hex(CIANO))
    canvas.circle(cx, cy, 2.4, stroke=0, fill=1)
    canvas.restoreState()


def _section_bar(numero: str, titulo: str, subtitulo: str = ""):
    out = [Paragraph(
        f'<font color="{CIANO}">{numero}</font>&nbsp;&nbsp;{_P(titulo)}', SECTION)]
    if subtitulo:
        out.append(Paragraph(subtitulo, MUTED))
    return out


def _card(accent: str, flow, pad=9):
    """Card com barra de acento lateral esquerda."""
    t = Table([["", flow]], colWidths=[0.16 * cm, 16.84 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), _hex(accent)),
                ("BACKGROUND", (1, 0), (1, 0), _hex(PANEL)),
                ("BOX", (0, 0), (-1, -1), 0.7, _hex(LINHA)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (1, 0), (1, 0), pad),
                ("RIGHTPADDING", (1, 0), (1, 0), pad),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ]
        )
    )
    return t


# ── Gráficos (tema escuro) ────────────────────────────────────────────────────

def gerar_donut(path: Path) -> None:
    valores = [CONTAGENS_SEVERIDADE[k] for k in ORDEM_SEV]
    rotulos = [PDFMETRICS[k] for k in ORDEM_SEV]
    cores = [HEX_SEV[k] for k in ORDEM_SEV]
    fig, ax = plt.subplots(figsize=(5.1, 3.1), dpi=200)
    fig.patch.set_facecolor(BG)
    wedges, _, autot = ax.pie(
        valores,
        colors=cores,
        startangle=100,
        counterclock=False,
        autopct=lambda pct: f"{pct:.0f}%" if pct > 0 else "",
        pctdistance=0.78,
        wedgeprops=dict(width=0.40, edgecolor=BG, linewidth=2),
    )
    for w, c in zip(wedges, cores):
        w.set_edgecolor(c)
    for at in autot:
        at.set_color("#E2E8F0")
        at.set_fontsize(7.5)
        at.set_fontweight("bold")
    centro = sum(valores)
    ax.text(0, 0.09, str(centro), ha="center", va="center", fontsize=24,
            fontweight="bold", color="#F8FAFC")
    ax.text(0, -0.14, "achados", ha="center", va="center", fontsize=8.5, color="#94A3B8")
    ax.axis("equal")
    handles = [w for w, c in zip(wedges, valores) if c > 0]
    labels = [f"{r}: {c}" for r, c in zip(rotulos, valores) if c > 0]
    ax.legend(
        handles, labels, loc="center left", bbox_to_anchor=(1.02, 0.5),
        fontsize=8, frameon=False, labelcolor="#CBD5E1", handlelength=1.1,
    )
    fig.tight_layout(pad=0.4)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def gerar_barras(path: Path) -> None:
    cats = list(CONTAGENS_CATEGORIA.keys())
    vals = list(CONTAGENS_CATEGORIA.values())
    curtos = [c.replace(" — ", "\n") for c in cats]
    cores_cat = [HEX_SEV["alta"], HEX_SEV["media"], "#CBD5E1", HEX_SEV["baixa"], HEX_SEV["info"]]
    n = len(cats)
    ypos = range(n)
    fig, ax = plt.subplots(figsize=(6.4, 3.2), dpi=200)
    fig.patch.set_facecolor(BG)
    ax.patch.set_facecolor(BG)
    bars = ax.barh(list(ypos), vals, color=cores_cat, height=0.6, edgecolor=BG, linewidth=2)
    for b, v in zip(bars, vals):
        if v > 0:
            ax.text(b.get_width() + 0.12, b.get_y() + b.get_height() / 2, str(v),
                    va="center", ha="left", fontsize=9.5, fontweight="bold", color="#F8FAFC")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(curtos, fontsize=6.6, color="#CBD5E1")
    ax.set_xlim(0, max(vals) * 1.25 + 0.6)
    ax.set_ylim(-0.6, n - 0.4)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors="#94A3B8", labelsize=8)
    ax.xaxis.grid(True, color="#1E293B", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.4)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


# ── Montagem do documento ──────────────────────────────────────────────────────
def _build_story():
    story = []

    # ══ CAPA ══════════════════════════════════════════════════════════════════
    story.append(Paragraph(
        f'<font name="UbuntuMono" color="{CIANO}">DB://SECURITY-AUDIT // STUDYAGENT</font>', BADGE))
    story.append(Paragraph("Relatório de Auditoria", TITULO))
    story.append(Paragraph(
        f'<font color="{CIANO}">de Segurança</font> '
        f'<font name="Ubuntu-Light" color="{TX_NEUTRO}">— StudyAgent</font>', TITULO))
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph(
        f'Avaliação estática de <b>segurança da informação</b> em backend FastAPI, frontend '
        f'React, ferramentas do agente, deploy e histórico git.', SUB))
    story.append(Spacer(1, 0.5 * cm))
    t_hero = Table([["", "", ""]], colWidths=[4.0 * cm, 6.0 * cm, 7.0 * cm])
    t_hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), _hex(CIANO)),
        ("BACKGROUND", (1, 0), (1, 0), _hex(VIOLETA)),
        ("BACKGROUND", (2, 0), (2, 0), _hex(ROSA)),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_hero)
    story.append(Spacer(1, 0.6 * cm))
    stats = [
        ("9", "achados", "#F8FAFC"),
        ("3", "alta severidade", HEX_SEV["alta"]),
        ("2", "média severidade", HEX_SEV["media"]),
        ("2", "baixa severidade", HEX_SEV["baixa"]),
        ("13", "pontos fortes", HEX_SEV["forte"]),
    ]
    cab_cells = []
    for num, lab, cor in stats:
        cab_cells.append(
            Paragraph(
                f'<font name="Ubuntu-Bold" color="{cor}" size="19">{num}</font><br/>'
                f'<font color="{TX_NEUTRO}" size="7.2" name="Ubuntu">{_esc(lab)}</font>',
                ParagraphStyle("stat", alignment=TA_CENTER, leading=11),
            )
        )
    t_stats = Table([cab_cells], colWidths=[17.0 * cm / 5] * 5)
    t_stats.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _hex(PANEL)),
                ("BOX", (0, 0), (-1, -1), 0.7, _hex(LINHA)),
                ("GRID", (0, 0), (-1, -1), 0.3, _hex(LINHA)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(t_stats)
    story.append(Spacer(1, 0.5 * cm))
    escopo = (
        f"<b>Escopo auditado:</b> StudyAgent — backend FastAPI/Python (routers, agent/tools, "
        f"tutor, security, core), frontend React/TypeScript/Vite, deploy (Dockerfile, "
        f"docker-compose, systemd, CI GitHub Actions), config (permissions.json, .env/.env.example) "
        f"e histórico git."
    )
    story.append(Paragraph(
        f'<b>Fechamento:</b> {DATA_AUDITORIA} &nbsp;&nbsp; <b>Método:</b> auditoria estática '
        f'verificada (evidência por arquivo:linha)', META))
    story.append(Spacer(1, 0.1 * cm))
    story.append(_card(CIANO, Paragraph(escopo, BODY)))
    story.append(Spacer(1, 0.4 * cm))
    nota = (
        f"<b>Nota metodológica (mapeamento das categorias para a stack).</b> O projeto é um app "
        f"local single-user (SQLite, sem ORM; auth por PIN local via header X-StudyAgent-Pin; sem "
        f"conceito de usuário/tenant). As categorias foram adaptadas: "
        f"(1) 'Banco sem trava' → controle de quem acessa os dados da API, já que RLS/tenant não "
        f"existe — o equivalente é a ausência de autenticação/autorização na leitura de documentos, "
        f"conversas, perfil, faces e estatísticas. "
        f"(2) 'Permissão definida no navegador' → cruzamento do painel de permissões/PIN no "
        f"frontend com o que o backend realmente valida em cada rota sensível. "
        f"(3) IDOR → não aplicável como multi-usuário; o equivalente (objeto por ID sem autorização) "
        f"foi verificado em todos os handlers e é coberto pelo achado A1. "
        f"(4) Chaves expostas → varredura do código, configs, deploy, histórico git e bundle dist do "
        f"frontend. "
        f"(5) Inputs sem tratamento → XSS no frontend/backend e SSRF via tools web."
    )
    story.append(_card(VIOLETA, Paragraph(_djv(nota), BODY)))
    story.append(PageBreak())

    # ══ RESUMO EXECUTIVO ═══════════════════════════════════════════════════════
    story.extend(_section_bar("01", "Resumo executivo"))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Foram verificados todos os routers do backend (chat, screen, exercises, documents, "
        f"audio, audio_stream, facial, tutor, health), o pipeline do agente e tools, o frontend "
        f"(todos os componentes), os arquivos de deploy e o histórico git. Resultado: "
        f'<font color="{HEX_SEV["alta"]}"><b>9 achados</b></font> '
        f"(0 críticos, 3 altos, 2 médios, 2 baixos, 2 informativos) e "
        f'<font color="{HEX_SEV["forte"]}"><b>13 pontos fortes</b></font> confirmados, incluindo '
        f"a ausência de SQL injection, de XSS clássico e de segredos no git.",
        BODY,
    ))
    story.append(Spacer(1, 0.4 * cm))
    dados = [
        [Paragraph(f'<font color="{CIANO}"><b>Distribuição por severidade</b></font>', H2),
         Paragraph(f'<font color="{CIANO}"><b>Distribuição por categoria</b></font>', H2)],
        [
            Image(str(CHARTS_DIR / "donut.png"), width=7.9 * cm, height=4.8 * cm),
            Image(str(CHARTS_DIR / "barras.png"), width=8.7 * cm, height=4.35 * cm),
        ],
    ]
    t_graf = Table(dados, colWidths=[8.0 * cm, 9.0 * cm])
    t_graf.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 1), (-1, 1), _hex(PANEL)),
                ("BOX", (0, 1), (-1, 1), 0.7, _hex(LINHA)),
                ("LEFTPADDING", (0, 1), (-1, 1), 6),
                ("RIGHTPADDING", (0, 1), (-1, 1), 6),
                ("TOPPADDING", (0, 1), (-1, 1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
            ]
        )
    )
    story.append(t_graf)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f'<font color="{ROSA}"><b>PONTOS FRACOS CENTRAIS (RISCOS)</b></font>', H2))
    story.append(Spacer(1, 0.15 * cm))
    riscos = [
        ("Ausência total de autenticação na API",
         " → dados pessoais (documentos, conversas, biometria, perfil) legíveis sem "
         f'credencial <font color="{HEX_SEV["alta"]}">[A1]</font>'),
        ("Aprovação de automação sem PIN",
         " → contrariando a própria especificação do projeto; confirmação é só um botão "
         f'no navegador <font color="{HEX_SEV["alta"]}">[A2]</font>'),
        ("SSRF via web_search/open_url",
         " → com permissão internet ativa por padrão e sem bloqueio de redes internas — "
         f'explorável via prompt injection <font color="{HEX_SEV["alta"]}">[A7]</font>'),
    ]
    for tit, desc in riscos:
        flow = Paragraph(_djv(f'{D("⚠")}&nbsp;<b>{_esc(tit)}</b>{desc}'), BODY)
        story.append(_card(HEX_SEV["alta"], flow, pad=7))
        story.append(Spacer(1, 0.18 * cm))
    story.append(PageBreak())

    # ══ PONTOS FORTES E FRACOS ═════════════════════════════════════════════════
    story.extend(_section_bar(
        "02", "Pontos fortes e fracos",
        "Forças com evidência (localização verificada) e riscos centrais consolidados."))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(f'<font color="{MENTA}"><b>PROTEGIDO — PONTOS FORTES</b></font>', H2))
    story.append(Spacer(1, 0.15 * cm))
    for titulo, desc in PONTOS_FORTES:
        flow = Paragraph(
            f'<font color="{MENTA}"><b>{D("✓")}</b></font>&nbsp; '
            f"<b>{_P(titulo)}.</b> {_P(desc)}", BODY)
        story.append(_card(MENTA, flow, pad=7))
        story.append(Spacer(1, 0.16 * cm))
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph(f'<font color="{ROSA}"><b>FRACOS — RISCOS CENTRAIS</b></font>', H2))
    story.append(Spacer(1, 0.15 * cm))
    fracos = [
        "Sem barreira de autenticação entre consumidor local/remoto e a API (A1).",
        "Consentimento de automação validado apenas na UI (A2).",
        "Busca na web e abertura de URL sem restrição de destino (A7).",
        "Inconsistência de permissão no módulo de documentos (A3) e PIN em claro no disco (A5).",
        "Endurecimento ausente: sem validação de startup, sem security headers, rotas mortas (A6/A8/A9).",
    ]
    for item in fracos:
        flow = Paragraph(f'{D("●")}&nbsp;{_P(item)}', BODY)
        story.append(_card(ROSA, flow, pad=7))
        story.append(Spacer(1, 0.16 * cm))
    story.append(PageBreak())

    # ══ TABELA DE ACHADOS ══════════════════════════════════════════════════════
    story.extend(_section_bar("03", "Achados detalhados por categoria"))
    story.append(Spacer(1, 0.15 * cm))
    info = (
        f"IDOR (C3): não aplicável como multi-usuário — não existe conceito de dono/tenant. O acesso "
        f"a objetos por ID (doc_id, session_id, deck_id, plan_id, card_id, proposal_id, error_id, name) "
        f"sem verificação de autorização é o equivalente e está coberto pelo achado A1, confirmado na "
        f"revisão sistemática de todos os handlers."
    )
    story.append(Paragraph(f'{D("▶", color=CIANO)}&nbsp; {info}', MUTED))
    story.append(Spacer(1, 0.3 * cm))

    header = [
        Paragraph("ID", CELLID),
        Paragraph("Severidade", CELLID),
        Paragraph("Categoria", CELLID),
        Paragraph("Arquivo:linha", CELLID),
        Paragraph("Descrição", CELLID),
    ]
    rows = [header]
    for a in ACHADOS:
        sev = a["severidade"]
        chip = Paragraph(
            _esc(PDFMETRICS[sev]),
            ParagraphStyle("chipc", alignment=TA_CENTER, leading=9,
                           backColor=HEX_SEV[sev], borderPadding=(2, 4, 2, 4),
                           fontSize=7.2, fontName="Ubuntu-Bold", textColor=colors.HexColor(BG)),
        )
        rows.append(
            [
                Paragraph(f'{D("◆", color=HEX_SEV[sev])} A{a["id"][1:]}', CELLID),
                chip,
                Paragraph(f"C{a['categoria'][1:]}", CELLID),
                Paragraph(_P(a["ref"]), CELLID),
                Paragraph(_P(a["titulo"]), CELLID),
            ]
        )
    t_ach = Table(rows, colWidths=[1.8 * cm, 1.9 * cm, 1.8 * cm, 4.6 * cm, 6.9 * cm], repeatRows=1)
    t_ach.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _hex("#111A2E")),
                ("GRID", (0, 0), (-1, -1), 0.4, _hex(LINHA)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_hex("#0B1220"), _hex("#0E1626")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t_ach)
    story.append(Spacer(1, 0.5 * cm))

    # ══ DETALHAMENTO DOS ACHADOS ═══════════════════════════════════════════════
    story.extend(_section_bar(
        "04", "Detalhamento dos achados",
        "Cada achado com descrição, evidência (arquivo:linha), explorabilidade, impacto, correção e critérios de aceite."))
    story.append(Spacer(1, 0.3 * cm))

    cats = {
        "C1": "C1 — Banco sem trava (isolamento)",
        "C2": "C2 — Permissão definida no navegador",
        "C3": "C3 — IDOR",
        "C4": "C4 — Chaves expostas",
        "C5": "C5 — Inputs sem tratamento (XSS)",
    }
    for a in ACHADOS:
        sev = a["severidade"]
        cor = HEX_SEV[sev]
        conteudo = []
        conteudo.append(Paragraph(
            f'{D("◆", color=cor)} <b>A{a["id"][1:]}</b> · {_P(a["titulo"])}', ACHTIL))
        conteudo.append(Spacer(1, 1))
        conteudo.append(Paragraph(
            f'SEVERIDADE <font color="{cor}">{_esc(PDFMETRICS[sev].upper())}</font>'
            f'&nbsp;&nbsp;·&nbsp;&nbsp;CATEGORIA <font color="{TX_NEUTRO}">{_P(cats.get(a["categoria"], a["categoria"]))}</font>'
            f'&nbsp;&nbsp;·&nbsp;&nbsp;REF <font color="{TX_NEUTRO}">{_P(a["ref"])}</font>', ACHMETA))
        conteudo.append(Spacer(1, 4))
        conteudo.append(Paragraph(
            f'<font color="{TX_NEUTRO}"><b>DESCRIÇÃO</b></font><br/>{_P(a["descricao"])}', BODY))
        conteudo.append(Spacer(1, 3))
        conteudo.append(Paragraph(
            f'<font color="{CIANO}"><b>EVIDÊNCIA (arquivo:linha)</b></font>', ACHMETA))
        conteudo.append(Paragraph(_P(a["evidencia"]), CODES))
        conteudo.append(Spacer(1, 3))
        conteudo.append(Paragraph(
            f'<font color="{ROSA}"><b>POR QUE É EXPLORÁVEL</b></font><br/>{_P(a["porque"])}', BODY))
        conteudo.append(Spacer(1, 3))
        conteudo.append(Paragraph(
            f'{D("⚠", color=cor)} <font color="{cor}"><b>IMPACTO</b></font><br/>{_P(a["impacto"])}', BODY))
        conteudo.append(Spacer(1, 3))
        conteudo.append(Paragraph(
            f'{D("▸", color=MENTA)} <font color="{MENTA}"><b>SUGESTÃO DE CORREÇÃO</b></font><br/>{_P(a["correcao"])}', BODY))
        conteudo.append(Spacer(1, 3))
        for i, c in enumerate(a["aceite"], start=1):
            conteudo.append(Paragraph(
                f'<font color="{TX_NEUTRO}">[ ]</font> <font color="{CIANO}">crit.{i}</font>&nbsp; '
                f'{_P(c)}', BODY))
        story.append(_card(cor, list(conteudo), pad=10))
        story.append(Spacer(1, 0.4 * cm))
    story.append(PageBreak())

    # ══ RECOMENDAÇÕES ══════════════════════════════════════════════════════════
    story.extend(_section_bar(
        "05", "Recomendações priorizadas",
        "Ordem de execução sugerida: P1 (bloqueante) → P2 (curto prazo) → P3 (endurecimento)."))
    story.append(Spacer(1, 0.3 * cm))
    prec = {"P1": HEX_SEV["alta"], "P2": HEX_SEV["media"], "P3": HEX_SEV["baixa"]}
    for p, titulo, desc in RECOMENDACOES:
        cor = prec.get(p, HEX_SEV["baixa"])
        tag = Paragraph(
            f'<font name="Ubuntu-Bold" color="{BG}">{p}</font>',
            ParagraphStyle("ptag", alignment=TA_CENTER, leading=12, backColor=cor,
                           borderPadding=(2, 5, 2, 5), fontSize=9.5),
        )
        corpo = Paragraph(
            f'<font color="{cor}"><b>{_P(titulo)}</b></font><br/>{_P(desc)}', BODY)
        row = Table([[tag, corpo]], colWidths=[1.4 * cm, 15.6 * cm])
        row.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), _hex(PANEL)),
                    ("BACKGROUND", (1, 0), (1, 0), _hex(PANEL)),
                    ("BOX", (0, 0), (-1, -1), 0.7, _hex(LINHA)),
                    ("LINEBEFORE", (1, 0), (1, 0), 2.0, _hex(cor)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(row)
        story.append(Spacer(1, 0.25 * cm))
    story.append(PageBreak())

    # ══ ISSUES PARA GITHUB ═════════════════════════════════════════════════════
    story.extend(_section_bar(
        "06", "Issues para o GitHub",
        "Blocos prontos para copiar e colar na aba Issues — título, labels, exploração, evidência, impacto, correção e aceite."))
    story.append(Spacer(1, 0.3 * cm))
    for i, issue in enumerate(ISSUES, start=1):
        head = Paragraph(
            f'<font color="{CIANO}">ISSUE</font>&nbsp;'
            f'<font color="{TX_FORTE}">{i}</font>&nbsp;&nbsp;'
            f'<font name="Ubuntu" color="{TX_NEUTRO}" size="8">{_P(issue["titulo"])}</font>', ISSH)
        story.append(_card(CIANO, head, pad=8))
        story.append(Spacer(1, 0.12 * cm))
        linhas = (f"--- ISSUE {i} ---\n### {issue['titulo']}\nLabels: `{issue['labels']}`\n\n"
                  f"{issue['body']}\n--- FIM ISSUE {i} ---\n").split("\n")
        partes = []
        for ln in linhas:
            e = _P(ln)
            if ln.startswith("--- ISSUE") or ln.startswith("--- FIM"):
                partes.append(f'<font color="{CIANO}"><b>{e}</b></font>')
            elif ln.startswith("Labels:"):
                partes.append(f'<font color="{HEX_SEV["media"]}">{e}</font>')
            elif ln.startswith("### "):
                partes.append(f'<font color="{TX_FORTE}"><b>{e}</b></font>')
            elif ln.startswith("## "):
                partes.append(f'<font color="{CIANO}"><b>{e}</b></font>')
            elif ln.startswith("- [ ]"):
                partes.append(f'<font color="{TX_NEUTRO}">{e}</font>')
            else:
                partes.append(e)
        bloco = "<br/>".join(partes)
        code = Paragraph(bloco, CODES)
        t_code = Table([[code]], colWidths=[16.84 * cm])
        t_code.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _hex("#0A0F1A")),
                    ("BOX", (0, 0), (-1, -1), 0.7, _hex("#223047")),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.0, _hex(CIANO)),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(t_code)
        story.append(Spacer(1, 0.45 * cm))

    return story


def main():
    global TOTAL
    _registrar_fontes()
    gerar_donut(CHARTS_DIR / "donut.png")
    gerar_barras(CHARTS_DIR / "barras.png")

    def _montar():
        return SimpleDocTemplate(
            str(OUT_PDF),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=RELATORIO_NOME,
            author="Auditoria de Segurança",
            subject="Relatório de auditoria de segurança — StudyAgent",
        )

    doc1 = _montar()
    doc1.build(_build_story(), onFirstPage=_capa, onLaterPages=_fundo)
    TOTAL = doc1.page
    doc2 = _montar()
    doc2.build(_build_story(), onFirstPage=_capa, onLaterPages=_fundo)
    print(f"OK -> {OUT_PDF} ({TOTAL} páginas)")


if __name__ == "__main__":
    main()