# Risk Register — StudyAgent

Registro de riscos técnicos, de segurança e operacionais levantados na auditoria
(2026-09-01), com prioridade P0–P3 e plano de tratamento. Reflete o código real.

## Cabeçalho

**Critérios:** P0 = bloqueia/deve ser corrigido antes de qualquer feature;
P1 = alta prioridade (confiança/dados); P2 = importante; P3 = melhoria futura.

## Riscos de segurança

| # | Risco | Evidência | Severidade | Estado |
|---|---|---|---|---|
| R1 | `config/permissions.json` versionado com `mouse_control`, `keyboard_control`, `command_execution` iguais a `true` → um clone nasce com execução de comandos liberada (merge em `permissions.py:66-68` sobrescreve o fail-closed do código) | `config/permissions.json:7-9` | **P0** | 🔧 corrigir |
| R2 | Frontend Docker publicado em todas as interfaces (`5173:80`) sem bind localhost, contradizendo "local only"; sem autenticação nem proxy reverso no host | `docker-compose.yml:27` | **P0** | 🔧 corrigir |
| R3 | Sem testes automatizados de segurança (PIN, rate limiting, CORS, autorização nos routers, prompt injection) | testes analisados (nenhum `TestClient`/`httpx`) | **P0** | 🔧 corrigir |
| R4 | `backend/.env` (gitignored) com `STUDYAGENT_PIN` no working tree; backup/inclusão inadvertida expõe o segredo | `backend/.env:4`, `.gitignore:17` | P0 | contido p/ git, risco residual. Manter fora de `git add -A` e de backup |
| R5 | `backup.sh` grava em `backages/` (typo) que **não está no `.gitignore`**; `.api.pid`/`.web.pid` também não → `git add .` captura DB de alunos + segredos | `backup.sh:6`, `.gitignore` | P1 | pendente |
| R6 | `update.sh:35` faz `git stash` silencioso → pode esconder/pender alterações locais e segredos | `update.sh` | P1 | pendente |
| R7 | `stop.sh:39-44` mata **qualquer** `uvicorn app.main:app` do sistema (pode derrubar processos de outros projetos) | `stop.sh` | P2 | pendente |
| R8 | Bootstraps executam código remoto (`curl \| sh`, `iex`) sem pin/checksum (supply-chain) | `setup.sh:188`, `install.ps1:13-14` | P2 | aceito/documentar |
| R9 | Docker sem usuário não-root; sem HEALTHCHECK no frontend | Dockerfile, frontend/Dockerfile | P2 | 🔧 corrigir (FASE 2-a) |
| R10 | Listener (`viva-voz`) sem healthcheck/watchdog; hang de áudio não reinicia | `scripts/studyagent-listener.service:10` | P2 | pendente |
| R11 | `scripts/*.service` não são instalados pelo `install.sh` (divergência entre referência e instalado) → doctor reporta serviço ausente | `install.sh:109-145` vs `scripts/*.service` | P1 | pendente |

## Riscos técnicos / de dados

| # | Risco | Evidência | Severidade | Estado |
|---|---|---|---|---|
| R12 | `backup.sh` copia o banco do caminho **errado** (`$ROOT/backend/data/...` vs real `$ROOT/data/memory/studyagent.db` em `config.py:10`) → **o backup nunca contém o banco** (só permissions.json + rag/*.npz) | `backup.sh:23-25,51` | **P0*** | pendente (P1 executar) |
| R13 | XP/conquistas concedidos "oportunisticamente" no frontend (não sincronizados com `/api/level`); `addXp` depende de StatsPanel ter aberto o store | `userStore.ts:26`, `useChat.ts:105` | P2 | pendente |
| R14 | `ActionConfirm` busca ações pendentes só no mount; novas propostas do agente só aparecem após reload | `ActionConfirm.tsx:13-15` | P2 | pendente |
| R15 | Polling agressivo: preview de tela 2s + watch loop `/api/chat` ~25s sem abort | `useScreen.ts:28,51`, `LivePanel.tsx:45-50` | P2 | pendente |
| R16 | Erros não tratados: `getPermissions` sem `.catch` no panel; `getMonitors`/recs sem tratamento → rejeição não capturada | `api.ts:110-113`, `useScreen.ts:27`, `StatsPanel.tsx:46-51` | P2 | pendente |
| R17 | Duplicidade de `StudyAgent()` (chat/documents/screen) — instâncias separadas do agente sem estado compartilhado proposital | `chat.py:19`, `documents.py:17`, `screen.py:16` | P3 | aceito (design atual) |
| R18 | `/api/audio/speak` não verifica permissão de microfone (só `/transcribe` exige) | `routers/audio.py` | P2 | pendente |
| R19 | Dependências sem pin em `requirements.txt` (nenhuma versão) → builds não reproduzíveis | `requirements.txt` | P2 | pendente |
| R20 | Sem teste de integração com banco real (todos usam `get_connection` mockado em 11 módulos) | `conftest.py:146` | P1 | pendente |

## Riscos de performance

| # | Risco | Evidência | Severidade | Estado |
|---|---|---|---|---|
| R21 | `doctor.sh` executa inferência real (llama3.1 30s + embeddings 30s + screen diagnostics 15s) sequencial → diagnóstico lento | `doctor.sh:322-366,506` | P2 | pendente (modo --quick) |
| R22 | Painéis remontam do zero ao reabrir (4+ chamadas em StatsPanel, 3 em Achievements) | `StatsPanel.tsx:24` | P2 | pendente |
| R23 | Sem debounce real no input de chat (hook `useDebounce` órfão) | `hooks/useDebounce.ts` | P3 | pendente |

## Pontos fortes (manter)

- Default fail-closed + `hmac.compare_digest` no PIN; 401 quando `STUDYAGENT_PIN` ausente.
- CORS restrito a localhost:5173/127.0.0.1:5173.
- Rate limiting (slowapi) em chat/exercícios/correção/flashcards/planos/áudio/facial/actions.
- Backend publishado só em `127.0.0.1` (start.sh/install.sh/docker-compose backend).
- Sem `shell=True`; calculadora AST-safe; CSV/filename sanitizados (rodada anterior).
- Logging estruturado com request_id; health check 6 componentes; exception handler 500 seguro.
- Sem segredos rastreados no git (backend/.env gitignored).

## Tranqueiras de tratamento

- **P0 (rodadas atuais):** R1, R2, R3 → permissões perigosas off no arquivo versionado; bind `127.0.0.1:5173:80` + non-root + HEALTHCHECK; suíte de testes de segurança (PIN/rate-limit/CORS/routers).
- **P1 (próximas):** R12 backup path real (+ `.gitignore` para `backages/`/`.pid`), R5, R11, R20.
- **P2:** R6, R7, R9, R10, R13, R14, R15, R16, R18, R19, R21, R22.
- **P3:** R17, R23.