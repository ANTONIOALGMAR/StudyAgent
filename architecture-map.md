# Architecture Map — StudyAgent

Mapa arquitetural atual do StudyAgent (a partir da auditoria de 2026-09-01).
Documento de referência para evolução incremental; reflete o código real.

## 1. Visão geral

```
UI (React 18 + TS, shell único, sem roteador)
  ↓ http://localhost:8000 (hardcode em frontend/src/api.ts:1; CORS fixo em backend/app/main.py:63)
API (FastAPI, 8 routers, ~50 endpoints)
  ├─ chat / screen / exercises / documents / audio / audio_stream
  ├─ tutor (~50 endpoints) / facial / health
  ↓
CORE / Orchestrator (backend/app/core/orchestrator/)
  ├─ planner:  decide captura de tela, monitor, estratégia de documento
  ├─ context_manager:  system prompt socrático + dashboard do aluno
  ├─ vision_router:    intenção visual, notas de imagem, OCR híbrido
  ├─ model_manager:    roteador de modelos por env (text/vision/coder/embedding/stt/tts)
  └─ registered_tools:  10 ferramentas (web_search, open_url, calculate, ...)
  ↓
AGENT (backend/app/agent/)
  ├─ agent.py        orquestra plano → ferramentas → resposta (MAX_STEPS, circuit breaker)
  ├─ memory.py       schema SQLite (21 tabelas de negócio)
  └─ exercises.py    gerador + corretor + grade_and_track (mastery weighted + XP)
  ↓
TUTOR (backend/app/tutor/)
  flashcards (SM-2) · study_plan · profile (weighted) · stats · automation
  advanced_profile · gamification (26 conquistas/XP/5 níveis) · error_notebook · export_import

VISION   screen[1] · engine · ocr (Tesseract) · window · facial (InsightFace)
AUDIO    stt · tts (Piper) · vad (puro numpy) · wake_word · listener · voice_streamer
TOOLS    calculator (AST-safe) · documents (extr+RAG) · rag (numpy/Chroma) · web_search
SECURITY permissions (JSON + auditoria + temporárias) · local_auth (PIN local_auth.py)
INFRA    install/start/stop/update/backup/doctor · systemd user · Docker (backend+frontend)
```

Fontes principais: `backend/app/main.py`, `backend/app/core/orchestrator/`, `backend/app/agent/`,
`backend/app/tutor/`, `backend/app/vision/`, `backend/app/audio/`, `backend/app/tools/`,
`backend/app/security/`, `frontend/src/App.tsx`, `frontend/src/components/`, `frontend/src/hooks/`,
`frontend/src/api.ts`.

## 2. Components e suas responsabilidades

| Componente | Caminho | Responsabilidade |
|---|---|---|
| FastAPI app | `app/main.py` | routers, CORS, rate limiting (slowapi), middleware request_id, exception handler |
| SQLite centralizado | `app/db.py` | conexão WAL thread-local (`_local`), `get_connection` |
| Schema DB | `app/agent/memory.py` (+`exercises.py`) | 21 tabelas de negócio + `exercise_store` |
| Orchestrator | `app/core/orchestrator/` | plan_builder → executor → circuit breaker, evidence, policies, validator |
| Vision Router | `app/core/vision_router.py` (1098 ln) | intenção visual, OCR híbrido, notas de imagem, roteia para modelo |
| Model Manager | `app/core/model_manager.py` | resolve modelo por papel/configuração |
| Agent | `app/agent/agent.py` (714 ln) | orquestra chat/ferramentas, memória rolante |
| Tutor | `app/tutor/*` | flashcards, planos, perfil, stats, automação, gamificação, erros, export |
| Visão | `app/vision/*` | screen (1271 ln), engine, ocr, window, facial |
| Áudio | `app/audio/*` | stt, tts, vad, wake_word, listener |
| Segurança | `app/security/*` | permissions (fail-closed), local_auth (PIN) |
| UI | `frontend/src/` | App shell, 15+ componentes, 5 hooks, api cliente |

## 3. Fluxo de uma requisição de chat

1. `Chat.tsx` → `useChat.sendText()` → `POST /api/chat` (`api.ts:42-67` com `session_id`, `use_screen`, `camera_image`, `doc_id`).
2. `routers/chat.py` cria/recupera instância `StudyAgent()` (`routers/chat.py:19`) e chama `agent.play(...)`.
3. Orchestrator constrói plano (planner + context_manager), executa ferramentas com circuit breaker, valida evidências e policy.
4. Resposta JSON volta com `session_id`, `response`, `tools_used`, `evidence` → `useChat` faz push no `ChatMessages`, aplica mood no avatar, concede XP.

## 4. Gerenciamento de permissões (uso real)

- Defaults **fail-closed** em `app/security/permissions.py:23-32` (perigosas `false`).
- `PermissionManager._load` faz `merged.update(arquivo)` → **arquivo `config/permissions.json` sobrescreve o default** (perigo: arquivo versionado com perigosas `true`, ver risk-register).
- `require()` é chamado nos módulos (microfone, câmera, tela, internet, etc.); emissão acontece via `set()`.
- Ativar permissões perigosas (`mouse_control`, `keyboard_control`, `command_execution`) exige PIN local (`local_auth.require_pin`, header `X-StudyAgent-Pin`; 401 fail-closed). Aplicado em `set_permission`, `set_permission_group`, `grant_temporary` (`routers/tutor.py`).
- Auditoria append-only em `config/permission_audit.json` (rotação 200 registros).

## 5. Memória (21 tabelas)

| Grupo | Tabelas | Finalidade |
|---|---|---|
| Conversa | `sessions`, `messages`, `summaries` | chat + resumos de sessão |
| Documentos | `documents` | uploads indexados |
| Aprendizagem | `exercise_history`, `exercise_store`, `flashcard_decks`, `flashcards`, `flashcard_reviews`, `study_plans`, `study_items` | exercícios, flashcards SM-2, planos |
| Perfil | `student_profile`, `topic_mastery`, `topic_results`, `adaptive_difficulty` | perfil + mastery weighted |
| Automação | `action_proposals`, `session_log` | propostas/confirmação |
| Gamificação | `achievements`, `student_xp`, `student_level` | conquistas/XP/níveis |
| Erros | `error_notebook` | caderno de erros |

## 6. Caminhos de execução (Infra)

- **Nativo/systemd**: `install.sh` grava units `studyagent-api.service` + `studyagent-web.service` (bind 127.0.0.1). Ollama via `start.sh` (`ollama serve &`); listener unit separada em `scripts/` (não instalada pelo install.sh).
- **Docker**: compose backend (`127.0.0.1:8000`) + frontend nginx (`5173:80`). Sem serviço Ollama no compose; env do compose usa `STUDYAGENT_*` não lidos pelo código.
- **doctor.sh**: diagnóstico read-only por seções, com inferência real (lento, ~1 min+), contadores pass/warn/fail.

## 7. Observabilidade

- Logging estruturado com `request_id`/`session_id` (`app/core/structured_logging.py`), middleware de request-id/timing (`main.py:48-56`).
- `/api/health` com 6 componentes (`app/core/health.py:126-136`).
- Sem métricas exportáveis (`/metrics`) e sem tracing por etapa do pipeline.

## 8. Decisões arquiteturais registradas

- App single-user local; autenticação via PIN local em vez de auth completo (compatível com a fase atual).
- Docker publica backend só em localhost (compose) mantendo `0.0.0.0` interno para nginx interno do frontend.
- Visual commands/ações sensíveis exigem proposta + aprovação (`automation`/`ActionConfirm`), nunca execução silenciosa.

## 9. Gap vs Master Prompt (resumo)

- **Temporal/Screen Diff**: inexistente; loop de análise sempre chama modelo.
- **Confidence/Evidence vs Mastery**: só weighted score; sem view separada.
- **Adaptive Review Scheduler / NBA**: recomendações por tempo existem; fila priorizada unificada não.
- **Math (LaTeX+sympy)**: inexistente.
- **Sleeping/estados avatar, ActionConfirm ao vivo, acessibilidade**: parcial (ver feature-matrix).
- **Observabilidade/Doctor 2.0, testes HTTP/segurança, env unificado, backup correto**: pendentes (P0/P1).

[1] `app/vision/screen.py` — captura multi-monitor (mss + cosmic-screenshot em Wayland).