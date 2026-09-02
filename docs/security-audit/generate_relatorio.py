# -*- coding: utf-8 -*-
"""Gerador do Relatório de Auditoria de Segurança — StudyAgent.

Uso (ambiente isolado):
    .venv/bin/python generate_relatorio.py

Dependências: reportlab, matplotlib (instaladas no venv local).
Saída: docs/security-audit/relatorio-auditoria-seguranca.pdf
Imagens dos gráficos: charts/*.png (geradas e embutidas).
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
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

# ── Paleta ─────────────────────────────────────────────────────────────────────
COL = {
    "critica": colors.HexColor("#B91C1C"),
    "alta": colors.HexColor("#EA580C"),
    "media": colors.HexColor("#D97706"),
    "baixa": colors.HexColor("#2563EB"),
    "info": colors.HexColor("#64748B"),
    "forte": colors.HexColor("#059669"),
    "fundo": colors.HexColor("#0F172A"),
    "cinza": colors.HexColor("#334155"),
    "cinza_claro": colors.HexColor("#E2E8F0"),
    "branco": colors.white,
    "preto": colors.HexColor("#0B1120"),
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
            "(exfiltração de serviços internos/metadados).",
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
    ("SQL totalmente parametrizado", "memory.py, tutor/*.py e export_import.py usam apenas placeholders '?' — nenhuma concatenação de SQL no código (varredura por execute(f\u2026/.format retornou 0)."),
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
DATA_AUDITORIA = "02/09/2026"


def _pagina_num(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(COL["cinza"])
    canvas.drawCentredString(A4[0] / 2.0, 0.75 * cm, f"{doc.page}")
    canvas.drawString(2 * cm, 0.75 * cm, RELATORIO_NOME)
    canvas.restoreState()


# ── Gráficos ───────────────────────────────────────────────────────────────────
HEX_SEV = {
    "critica": "#B91C1C",
    "alta": "#EA580C",
    "media": "#D97706",
    "baixa": "#2563EB",
    "info": "#64748B",
}


def gerar_donut(path: Path) -> None:
    valores = [CONTAGENS_SEVERIDADE[k] for k in ORDEM_SEV]
    rotulos = [PDFMETRICS[k] for k in ORDEM_SEV]
    cores = [HEX_SEV[k] for k in ORDEM_SEV]
    plt.figure(figsize=(5.4, 3.1), dpi=200)
    wedges, _, _ = plt.pie(
        valores,
        colors=cores,
        startangle=90,
        counterclock=False,
        autopct=lambda pct: f"{pct:.0f}%" if pct > 0 else "",
        pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5),
    )
    centro = sum(valores)
    plt.text(
        0, 0.08, str(centro), ha="center", va="center", fontsize=22, fontweight="bold", color="#0B1120"
    )
    plt.text(0, -0.16, "achados", ha="center", va="center", fontsize=9, color="#475569")
    handles = [w for w, c in zip(wedges, valores) if c > 0]
    plt.legend(
        handles,
        [f"{r}: {c}" for r, c in zip(rotulos, valores) if c > 0],
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=8,
        frameon=False,
    )
    plt.axis("equal")
    plt.tight_layout()
    plt.savefig(path, transparent=False, facecolor="white")
    plt.close()


def gerar_barras(path: Path) -> None:
    cats = list(CONTAGENS_CATEGORIA.keys())
    vals = list(CONTAGENS_CATEGORIA.values())
    plt.figure(figsize=(6.6, 3.2), dpi=200)
    cores_cat = ["#B45309", "#EA580C", "#CBD5E1", "#7C3AED", "#D97706"]
    bars = plt.bar(cats, vals, color=[cores_cat[i % len(cores_cat)] for i in range(len(cats))])
    for b, v in zip(bars, vals):
        if v > 0:
            plt.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 0.06,
                str(v),
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color="#0B1120",
            )
    plt.gca().set_ylim(0, max(vals) * 1.25 + 0.5)
    plt.xticks(rotation=16, ha="right", fontsize=7)
    plt.yticks(fontsize=8)
    plt.gca().set_axisbelow(True)
    plt.grid(axis="y", alpha=0.3, linewidth=0.6)
    for s in ("top", "right"):
        plt.gca().spines[s].set_visible(False)
    plt.tight_layout()
    plt.savefig(path, transparent=False, facecolor="white")
    plt.close()


# ── Estilos ────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()


def _st(name, **kw):
    return ParagraphStyle(name, **kw)


TITULO_P = _st("TituloP", fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=COL["preto"])
SUB_P = _st("SubP", fontName="Helvetica", fontSize=12, leading=16, textColor=COL["cinza"])
H1 = _st("H1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=COL["preto"], spaceAfter=8)
H2 = _st("H2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=COL["preto"])
BODY = _st("Body", fontName="Helvetica", fontSize=9.3, leading=13.2, textColor=COL["preto"], alignment=TA_JUSTIFY)
BODY_C = _st("BodyC", fontName="Helvetica", fontSize=9.3, leading=13, textColor=COL["preto"], alignment=TA_CENTER)
CELL = _st("Cell", fontName="Helvetica", fontSize=7.6, leading=10, textColor=COL["preto"])
CELLB = _st("CellB", fontName="Helvetica-Bold", fontSize=7.6, leading=10, textColor=COL["preto"])
SMALL = _st("Small", fontName="Helvetica-Oblique", fontSize=8, leading=11, textColor=COL["cinza"])
CHIP = _st("Chip", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white)


def chip_style(sev: str):
    mapa = {
        "critica": COL["critica"],
        "alta": COL["alta"],
        "media": COL["media"],
        "baixa": COL["baixa"],
        "info": COL["info"],
    }
    return mapa.get(sev, COL["info"])


def _build_story():
    story = []

    # ── Capa ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Relatório de Auditoria de Segurança", TITULO_P))
    story.append(Paragraph("StudyAgent", _st("Titulo2", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=COL["cinza"])))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Data: 02 de setembro de 2026", SUB_P))
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "Escopo auditado: StudyAgent — backend FastAPI/Python (routers, agent/tools, tutor, "
            "security, core), frontend React/TypeScript/Vite, deploy (Dockerfile, docker-compose, "
            "systemd, CI GitHub Actions), config (permissions.json, .env/.env.example) e histórico git.",
            SUB_P,
        )
    )
    story.append(Spacer(1, 0.6 * cm))

    nota = [
        [
            "",
            Paragraph(
                "<b>Nota metodológica (mapeamento das categorias para a stack)</b><br/>" 
                "O projeto é um app local single-user (SQLite, sem ORM; auth por PIN local via header "
                "X-StudyAgent-Pin; sem conceito de usuário/tenant). As categorias foram adaptadas: "
                "(1) 'Banco sem trava' → controle de quem acessa os dados da API, já que RLS/tenant não "
                "existe — o equivalente é a ausência de autenticação/autorização na leitura de "
                "documentos, conversas, perfil, faces e estatísticas. "
                "(2) 'Permissão definida no navegador' → cruzamento do painel de permissões/PIN no "
                "frontend com o que o backend realmente valida em cada rota sensível. "
                "(3) IDOR → não aplicável como multi-usuário; o equivalente (objeto por ID sem "
                "autorização) foi verificado em todos os handlers e é coberto pelo achado A1. "
                "(4) Chaves expostas → varredura do código, configs, deploy, histórico git e bundle "
                "dist do frontend. "
                "(5) Inputs sem tratamento → XSS no frontend/backend e SSRF via tools web.",
                BODY,
            ),
        ]
    ]
    t_nota = Table(nota, colWidths=[0.4, None])
    t_nota.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, COL["cinza"]),
                ("BACKGROUND", (0, 0), (-1, -1), COL["fundo"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ]
        )
    )
    story.append(t_nota)
    story.append(PageBreak())

    # ── Resumo executivo ──────────────────────────────────────────────
    story.append(Paragraph("Resumo executivo", H1))
    story.append(
        Paragraph(
            "Foram verificados todos os routers do backend (chat, screen, exercises, documents, "
            "audio, audio_stream, facial, tutor, health), o pipeline do agente e tools, o frontend "
            "(todos os componentes), os arquivos de deploy e o histórico git. Resultado: <b>9 achados</b> "
            "(0 críticos, 3 altos, 2 médios, 2 baixos, 2 informativos) e <b>13 pontos fortes</b> "
            "confirmados, incluindo a ausência de SQL injection, de XSS clássico e de segredos no git.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    dados = [
        [Paragraph("<b>Distribuição por severidade</b>", H2), Paragraph("<b>Distribuição por categoria</b>", H2)],
        [
            Image(str(CHARTS_DIR / "donut.png"), width=8.4 * cm, height=4.8 * cm),
            Image(str(CHARTS_DIR / "barras.png"), width=9.0 * cm, height=4.4 * cm),
        ],
    ]
    t_graf = Table(dados, colWidths=[8.1 * cm, 8.8 * cm])
    t_graf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(t_graf)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Pontos fracos centrais (riscos)", H2))
    for txt in [
        "1. Ausência total de autenticação na API → dados pessoais (documentos, conversas, biometria, perfil) legíveis sem credencial (A1).",
        "2. Aprovação de automação sem PIN, contrariando a própria especificação do projeto; confirmação é só um botão no navegador (A2).",
        "3. SSRF via web_search/open_url com permissão internet ativa por padrão e sem bloqueio de redes internas — explorável via prompt injection (A7).",
    ]:
        story.append(Paragraph(txt, BODY))
    story.append(PageBreak())

    # ── Pontos fortes e fracos ─────────────────────────────────────────
    story.append(Paragraph("Pontos fortes (protegido — com evidência)", H1))
    for titulo, desc in PONTOS_FORTES:
        story.append(Paragraph(f"<b>✓ {titulo}.</b> {desc}", BODY))
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Pontos fracos (riscos centrais)", H1))
    for item in [
        "Sem barreira de autenticação entre consumidor local/remoto e a API (A1).",
        "Consentimento de automação validado apenas na UI (A2).",
        "Busca na web e abertura de URL sem restrição de destino (A7).",
        "Inconsistência de permissão no módulo de documentos (A3) e PIN em claro no disco (A5).",
        "Endurecimento ausente: sem validação de startup, sem security headers, rotas mortas (A6/A8/A9).",
    ]:
        story.append(Paragraph(f"• {item}", BODY))
    story.append(PageBreak())

    # ── Tabela de achados ──────────────────────────────────────────────
    story.append(Paragraph("Achados detalhados por categoria", H1))
    info = (
        "<i>IDOR (C3): não aplicável como multi-usuário — não existe conceito de dono/tenant. O acesso "
        "a objetos por ID (doc_id, session_id, deck_id, plan_id, card_id, proposal_id, error_id, name) "
        "sem verificação de autorização é o equivalente e está coberto pelo achado A1, confirmado na "
        "revisão sistemática de todos os handlers.</i>"
    )
    story.append(Paragraph(info, SMALL))
    story.append(Spacer(1, 0.2 * cm))

    header = [Paragraph("ID", CELLB), Paragraph("Severidade", CELLB), Paragraph("Categoria", CELLB), Paragraph("Arquivo:linha", CELLB), Paragraph("Descrição", CELLB)]
    rows = [header]
    for a in ACHADOS:
        rows.append(
            [
                Paragraph(a["id"], CELLB),
                Paragraph(PDFMETRICS[a["severidade"]], CHIP),
                Paragraph(f"C{a['categoria'][1:]}", CELL),
                Paragraph(a["ref"], CELL),
                Paragraph(a["titulo"], CELL),
            ]
        )
    t_ach = Table(rows, colWidths=[1.2 * cm, 1.7 * cm, 4.3 * cm, 4.3 * cm, 5.4 * cm], repeatRows=1)
    t_ach.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COL["preto"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, COL["cinza_claro"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COL["cinza_claro"]]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    for i, a in enumerate(ACHADOS, start=1):
        cor = chip_style(a["severidade"])
        t_ach.setStyle(TableStyle([("BACKGROUND", (1, i), (1, i), cor)]))
    story.append(t_ach)

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Detalhamento dos achados", H1))
    for a in ACHADOS:
        sev = PDFMETRICS[a["severidade"]]
        cor = chip_style(a["severidade"])
        story.append(
            Paragraph(
                f'<font color="white"><b> A{a["id"][1:]} · {a["titulo"]} </b></font>',
                ParagraphStyle(
                    "achhead",
                    fontName="Helvetica-Bold",
                    fontSize=10,
                    leading=13,
                    textColor=colors.white,
                    backColor=cor,
                    borderPadding=(4, 6, 4, 6),
                    spaceBefore=10,
                ),
            )
        )
        cats = {
            "C1": "C1 — Banco sem trava (isolamento)",
            "C2": "C2 — Permissão definida no navegador",
            "C3": "C3 — IDOR",
            "C4": "C4 — Chaves expostas",
            "C5": "C5 — Inputs sem tratamento (XSS)",
        }
        story.append(
            Paragraph(
                f'<b>Categoria:</b> {cats.get(a["categoria"], a["categoria"])} &nbsp;&nbsp; '
                f'<b>Severidade:</b> {sev} &nbsp;&nbsp; <b>Referência:</b> {a["ref"]}',
                SMALL,
            )
        )
        for campo, val in [
            ("Descrição", a["descricao"]),
            ("Evidência", a["evidencia"]),
            ("Por que é explorável", a["porque"]),
            ("Impacto", a["impacto"]),
            ("Sugestão de correção", a["correcao"]),
        ]:
            story.append(Paragraph(f"<b>{campo}:</b> {val}", BODY))
        story.append(
            Paragraph(
                "<b>Critérios de aceite:</b> " + " ".join(f"({i + 1}) {c}" for i, c in enumerate(a["aceite"])),
                BODY,
            )
        )
        story.append(Spacer(1, 4))
    story.append(PageBreak())

    # ── Recomendações ─────────────────────────────────────────────────
    story.append(Paragraph("Recomendações priorizadas", H1))
    prec = {"P1": COL["critica"], "P2": COL["media"], "P3": COL["baixa"]}
    for p, titulo, desc in RECOMENDACOES:
        cor = prec.get(p, COL["baixa"])
        style = ParagraphStyle(
            "recc",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.white,
            backColor=cor,
            borderPadding=(3, 5, 3, 5),
        )
        story.append(Paragraph(f"{p} — {titulo}", style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(desc, BODY))
        story.append(Spacer(1, 6))
    story.append(PageBreak())

    # ── Issues para GitHub ─────────────────────────────────────────────
    story.append(Paragraph("Issues para o GitHub", H1))
    story.append(
        Paragraph(
            "Blocos prontos para copiar e colar na aba Issues. Cada bloco contém título, labels "
            "sugeridas, problema/explorabilidade, evidência (arquivo:linha), impacto, correção e "
            "critérios de aceite verificáveis. Os achados triviais foram agrupados numa única issue "
            "de hardening para evitar spam.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    for i, iss in enumerate(ISSUES, start=1):
        story.append(
            Paragraph(
                f'<font color="white"><b> ISSUE {i} </b></font>',
                ParagraphStyle(
                    "ish",
                    fontName="Helvetica-Bold",
                    fontSize=11,
                    leading=14,
                    textColor=colors.white,
                    backColor=COL["preto"],
                    borderPadding=(3, 6, 3, 6),
                    spaceBefore=10,
                ),
            )
        )
        bloco = (
            f"--- ISSUE {i} ---\n"
            f"### {iss['titulo']}\n"
            f"Labels: `{iss['labels']}`\n\n"
            f"{iss['body']}\n"
            f"--- FIM ISSUE {i} ---\n"
        )
        pala = ParagraphStyle(
            "codigo",
            fontName="Courier",
            fontSize=7.4,
            leading=9.8,
            textColor=COL["preto"],
            backColor=COL["cinza_claro"],
            borderPadding=(5, 6, 5, 6),
            borderColor=COL["cinza"],
            borderWidth=0.5,
        )
        story.append(Paragraph(bloco.replace("\n", "<br/>"), pala))
        story.append(Spacer(1, 6))

    return story


def main():
    gerar_donut(CHARTS_DIR / "donut.png")
    gerar_barras(CHARTS_DIR / "barras.png")

    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=RELATORIO_NOME,
        author="Auditoria de Segurança",
    )
    doc.build(_build_story(), onFirstPage=_pagina_num, onLaterPages=_pagina_num)
    print(f"OK -> {OUT_PDF}")


if __name__ == "__main__":
    main()