# Feature Matrix — StudyAgent

Inventário de funcionalidades existentes, parcialmente implementadas e planejadas
(a partir da auditoria de 2026-09-01). Legenda: ✅ completa · 🟡 parcial · ❌ faltante
· 🚫 fora de escopo/design.

## Backend — engines e agentes

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| Orchestrator V3 (plano→ferramentas→resposta) | ✅ | `app/core/orchestrator/` | circuit breaker, evidence, policies, validator |
| Planner (tela/monitor/documento) | ✅ | `app/core/planner.py` | |
| Context manager (socrático + dashboard) | ✅ | `app/core/context_manager.py` | |
| Model router por papel (env) | ✅ | `app/core/model_manager.py` | |
| Tool registry (10 ferramentas) | ✅ | `app/core/registered_tools.py` | web, calculadora, etc. |
| Intenção visual (vision router) | ✅ | `app/core/vision_router.py` (1098 ln) | OCR híbrido + notas |
| Coder model / CODE MENTOR | 🟡 | `model_manager` rotula coder | detecção real de stacktrace não há |
| Math solver determinístico (LaTeX+sympy) | ❌ | — | item Master Prompt §11 |
| Screen Diff / Temporal Vision | ❌ | — | item Master Prompt §6 |
| Fallback vision→OCR→texto | ✅ | `vision_router`/`ocr.py` | |
| Recuperação automática (retry/backoff/circuit) | ✅ | `app/core/orchestrator/circuit_breaker.py` | |

## Backend — tutoria e aprendizagem adaptativa

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| Flashcards SM-2 | ✅ | `app/tutor/flashcards.py` | intervalos, XP, stats |
| Planos de estudo mastery-aware | ✅ | `app/tutor/study_plan.py` | checklist + progresso |
| Mastery weighted (dificuldade/consistência/recência/volume) | ✅ | `app/tutor/profile.py` | P6 |
| Caderno de erros | ✅ | `app/tutor/error_notebook.py` | sem classificação de tipo de erro (§23) |
| Pipeline erro→flashcard | ✅ | `exercise→flashcard` | |
| Gamificação (26 conquistas, XP, 5 níveis, leaderboard) | ✅ | `app/tutor/gamification.py` | |
| Analytics temporal / recomendações por tempo | ✅ | `app/tutor/advanced_profile.py` | |
| Confidence vs Evidence (Knowledge Confidence §16) | 🟡 | weighted score só | falta view separada confidence/evidence |
| Zona de aprendizagem (UNKNOWN→MASTERED §15) | 🟡 | derivável do weighted | falta gate por evidências |
| Adaptive Review Scheduler (§24) | 🟡 | `due` + recomendações | falta fila priorizada unificada |
| Next Best Action (§44) | 🟡 | recomendações existem | falta camada NBA |
| Feynman Mode (§26) | ❌ | — | |
| Exam Mode (§27) | ❌ | — | |
| Teacher Mode (§28) | ❌ | — | |
| Proativas niveladas PROACTIVE_LEVEL (§47) | ❌ | — | |

## Backend — visão

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| Captura multi-monitor (X11/Wayland) | ✅ | `app/vision/screen.py` (1271 ln) | mss + cosmic-screenshot |
| OCR Tesseract (híbrido) | ✅ | `app/vision/ocr.py` | `shutil.which` após hardening |
| Janela ativa (xdotool/swaymsg) | ✅ | `app/vision/window.py` | |
| Reconhecimento facial (InsightFace) | ✅ | `app/vision/facial.py` | |
| Painel ao vivo + modo comentarista | ✅ | frontend `LivePanel` + `useScreen` | |
| OCR estruturado (títulos/tabelas/código/equações) | 🟡 | `ocr.read_text_structured` | layout/semantic segmentation (§10) incipiente |
| Screen Snapshot/Diff/Context/Event (§5-6) | ❌ | — | |
| Detecção de erro/stacktrace em tela (§30) | ❌ | — | |
| Modos Observador (OFF/ON-DEMAND/STUDY/...) (§7) | 🟡 | ON-DEMAND/commentator | modos explícitos não há |

## Backend — áudio

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| STT faster-whisper small | ✅ | `app/audio/speech_to_text.py` | |
| TTS Piper pt_BR | ✅ | `app/audio/text_to_speech.py` | |
| VAD por energia (puro numpy) | ✅ | `app/audio/vad.py` | testado |
| Wake word "ei study" | ✅ | `app/audio/wake_word.py` | |
| Listener viva-voz (daemon) | ✅ | `app/audio/listener.py` | sem healthcheck (R10) |
| Auditiva streaming / audiobook | ✅ | `audio_stream.py`, docs narration | |

## Backend — documentos, internet, dados

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| PDF/txt/md extração | ✅ | `app/tools/documents.py` | |
| Digest map-reduce + cache | ✅ | `app/tools/documents.py` | |
| RAG (embeddings nomic + cosine; integração Chroma) | ✅ | `app/tools/rag.py` | |
| Web search com fontes citadas | ✅ | `app/tools/web_search.py` | DDG→Bing→Wikipedia |
| PDF→curso / PDF→mapa de conhecimento (§21-22) | ❌ | — | |

## Segurança e auditoria

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| Permissões explícitas fail-closed | ✅ | `app/security/permissions.py:23-32` | ⚠ arquivo versionado pode sobrescrever (R1) |
| PIN local (STUDYAGENT_PIN + X-StudyAgent-Pin) | ✅ | `app/security/local_auth.py` | adicionado na rodada de hardening |
| Rate limiting (slowapi) | ✅ | routers | chat 15/min, exercícios 5/min, etc. |
| Auditoria de permissões (rotação) | ✅ | `permission_audit.json` | append-only 200 |
| Testes de segurança (TestClient) | ❌ | — | R3 — em construção |
| Privacy Center (§33) | ❌ | — | |
| Untrusted Content Boundary / anti-prompt-injection (§36) | 🟡 | web_search "destila/desambigua" | política explícita não há |
| Backup com banco correto | 🟡 | `backup.sh` path errado | R12 |

## Frontend — UX e humanização

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| Avatar 3D (estados, sync labial) | ✅ | `StudyAgent3D/*` | 13 estados |
| Estado `sleeping` no avatar | 🟡 | implementado mas inalcançável (`Chat.tsx:134-140`) | gatilho de inatividade falta |
| Painéis: exercícios/flashcards/plano/stats/perfil/conquistas | ✅ | `components/*Panel.tsx` | |
| Chat (mensagens, tela, voz, docs, action confirm) | ✅ | `Chat.tsx`, `useChat` | |
| ActionConfirm ao vivo (revalidação pós-resposta) | 🟡 | mount-only | R14 |
| Recomendações clicáveis (atalho→painel) | 🟡 | `StatsPanel` | |
| Acessibilidade (aria, reduced-motion, fontes) | 🟡 | parcial | baixo esforço (P2) |
| Teclado/hotkeys globais | ✅ | `Chat.tsx:97-117` | |
| Alto contraste / tamanho de fonte | 🟡 | — | |
| Modo palco / live / camera | ✅ | `Chat.tsx` | |

## Infra e observabilidade

| Funcionalidade | Estado | Evidência | Notas |
|---|---|---|---|
| install/start/stop/update/backup/doctor | ✅ | raiz + scripts/ | bacaré |
| Doctor 2.0 (`--quick/--json/--security`) | 🟡 | `doctor.sh` (701 ln) | sem modos; lento |
| Docker backend+frontend | ✅ | compose | R2 (bind) / R9 (root) |
| systemd user units | ✅ | install.sh + scripts/ | R11 (ollama/listener ausentes) |
| Métricas exportáveis / tracing | ❌ | — | |
| Logs JSON | 🟡 | texto custom | |
| Config por ambiente (dev/test/prod) | 🟡 | env divisão `STUDY_*`/`STUDYAGENT_*` | R19 |

## Testes

| Área | Estado | Quantidade |
|---|---|---|
| Backend (orquestrador, tutor, visão, gamificação, etc.) | ✅ | 469 |
| Frontend (unit + snapshot) | ✅ | 18 |
| API/HTTP (TestClient), segurança, CORS, rate limit | ❌ | 0 — em construção (R3) |
| Integração com banco real | 🟡 | mocks em 11 módulos |
| Prompt injection / pathtraversal / SSRF etc. | ❌ | até agora 0 |
| Cobertura medida (cov/CI thresholds) | ❌ | — |
| CI backend | ✅ | `.github/workflows/backend.yml` |
| CI frontend | ❌ | — |

## Roadmap de evolução (P0–P3, resumo)

**P0** — permissões perigosas off versionado · docker bind localhost + non-root + healthcheck · testes de segurança (PIN/rate-limit/CORS/routers).
**P1** — backup path real + `.gitignore` (backages/, *.pid) · install.sh units (ollama/listener) · doctor --quick/--json · teste integração banco real.
**P2** — Screen Diff/temporal + detecção de erro · Adaptive Review/NBA + Confidence/Evidence · `/metrics`+logs JSON · acessibilidade · env unificado · stop.sh seletivo · update.sh seguro.
**P3** — Feynman/Exam/Teacher mode · CODE MENTOR · math LaTeX+sympy · eventos (event bus) · benchmark cognitivo.

Detalhes em `roadmap-priorizado` (auditoria) e `risk-register.md`.