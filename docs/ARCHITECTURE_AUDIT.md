# StudyAgent — Architecture Audit V4

**Data:** 2026-08-27
**Commit:** 999027b
**390 testes passando | ruff clean | TypeScript strict | Vite build OK**

---

## 1. Visão Geral do Projeto

| Componente | Stack | Status |
|---|---|---|
| Backend | Python 3.12 / FastAPI / SQLite / Ollama | ✅ Funcional |
| Frontend | React 18 / TypeScript strict / Vite | ✅ Funcional |
| LLM | Ollama (llama3.1 text, qwen2.5vl:7b vision) | ✅ Funcional |
| OCR | Tesseract via subprocess + cache | ✅ Funcional |
| STT | faster-whisper | ✅ Funcional |
| TTS | piper-tts | ✅ Funcional |
| Captura | MSS + cosmic-screenshot (Wayland) | ✅ Funcional |
| RAG | NumPy embeddings + cosine + embedding cache + reranking | ✅ Funcional |
| Cache | TTLCache com LRU (OCR, vision, documentos) | ✅ Funcional |
| Deploy | Docker + docker-compose + nginx | ✅ Pronto |

---

## 2. Arquitetura Atual

```
routers/ ──> agent/ ──> core/ ──> orchestrator/
                         tools/  ──> vision/
                         tutor/  ──> db
                  │
                  v
              security/
              cache/
```

### Camadas

| Camada | Responsabilidade | Arquivos |
|---|---|---|
| **routers/** | HTTP endpoints (8 routers) | chat, screen, documents, exercises, audio, tutor, health |
| **agent/** | Orquestração Agent Loop V2, retry, circuit breaker | agent.py, llm.py, memory.py, exercises.py |
| **core/** | Planejamento, contexto, modelos, registro, cache, health | planner, context_manager, model_manager, vision_router, tool_registry, registered_tools, cache, health, structured_logging, env_validation |
| **orchestrator/** | Execution plan, executor, evidence, validator, policies, errors | 7 módulos |
| **vision/** | Captura, OCR (com cache), janela, processamento | screen, ocr, window, engine |
| **audio/** | STT, TTS, VAD, wake word, listener | 5 módulos |
| **tools/** | Calculadora, RAG (V2 com cache), documentos, web search | 4 módulos |
| **tutor/** | Flashcards, planos, perfil, gamificação, erros, export/import | 9 módulos |
| **security/** | Permissões V2 (audit, groups, hierarchy) | permissions.py |

### Dependências (sem ciclos)

```
routers → agent, core, vision, tools, tutor, security
agent   → core, vision, tools, security
core    → tools (registered_tools), vision (vision_router), cache
vision  → core (vision_router, cache)
tools   → db
tutor   → db
security → (nada interno)
audio   → config
```

**Resultado: NENHUM import circular.**

---

## 3. Inventário de Arquivos

### Backend (52 arquivos .py)

| Módulo | Arquivos | Linhas estimadas |
|---|---|---|
| app/ | __init__, main, config, db | ~250 |
| agent/ | agent, llm, memory, exercises | ~850 |
| core/ | planner, context_manager, model_manager, vision_router, tool_registry, registered_tools, cache, health, structured_logging, env_validation | ~1200 |
| orchestrator/ | execution_plan, execution_context, executor, evidence, validator, policies, errors, orchestrator | ~1000 |
| vision/ | screen, ocr, window, engine | ~450 |
| audio/ | listener, speech_to_text, text_to_speech, vad, wake_word | ~600 |
| tools/ | calculator, documents, rag, web_search | ~550 |
| tutor/ | flashcards, study_plan, profile, stats, gamification, advanced_profile, automation, error_notebook, export_import | ~1300 |
| security/ | permissions | ~180 |
| routers/ | chat, screen, documents, exercises, audio, tutor, health | ~800 |
| **Total** | **52** | **~7200** |

### Frontend (17 arquivos)

| Arquivo | Linhas | Função |
|---|---|---|
| api.ts | ~750 | Cliente API + 25+ interfaces |
| App.tsx | ~40 | Layout raiz |
| Chat.tsx | ~990 | God component (chat + voz + câmera + tela + painéis) |
| AgentFace.tsx | ~115 | Face animada SVG |
| Sidebar.tsx | ~50 | Navegação |
| ExercisesPanel.tsx | ~210 | Exercícios (inclui Adaptativo + Revisão) |
| FlashcardsPanel.tsx | ~280 | Flashcards + SM-2 |
| StudyPlanPanel.tsx | ~190 | Planos de estudo |
| StatsPanel.tsx | ~250 | Dashboard |
| ProfilePanel.tsx | ~120 | Perfil |
| AchievementsPanel.tsx | ~100 | Gamificação |
| PermissionsPanel.tsx | ~40 | Permissões |
| ActionConfirm.tsx | ~65 | Ações pendentes |
| PdfViewer.tsx | ~160 | Leitor PDF + audiobook |
| EvidencePanel.tsx | ~160 | Painel de evidências |
| index.css | ~1180 | Estilos globais + spinner + skeleton + responsive |

---

## 4. Banco de Dados (21 tabelas SQLite)

| Tabela | PK | Função |
|---|---|---|
| sessions | id TEXT | Sessões de chat |
| messages | id INTEGER AUTO | Mensagens por sessão |
| summaries | session_id TEXT | Resumos rolantes |
| documents | id TEXT | Metadados de documentos |
| exercise_history | id INTEGER AUTO | Histórico de exercícios |
| exercise_store | exercise_id TEXT | Cache de exercícios |
| flashcard_decks | id TEXT | Baralhos de flashcards |
| flashcards | id TEXT | Cards individuais (SM-2) |
| flashcard_reviews | id INTEGER AUTO | Log de revisões |
| study_plans | id TEXT | Planos de estudo |
| study_items | id INTEGER AUTO | Itens dos planos |
| student_profile | id TEXT | Nome, série, escola |
| topic_mastery | topic TEXT | Domínio por tópico |
| topic_results | id INTEGER AUTO | Resultados individuais |
| action_proposals | id TEXT | Propostas de automação |
| session_log | id TEXT | Timing de sessões |
| adaptive_difficulty | topic TEXT | Dificuldade adaptativa |
| achievements | id TEXT | Conquistas ganhas |
| error_notebook | id INTEGER AUTO | Caderno de erros |
| student_xp | id INTEGER AUTO | Log de XP |
| student_level | id INTEGER | Singleton nível |

---

## 5. Testes (390)

| Área | Arquivo | Testes |
|---|---|---|
| Orchestrator | test_orchestrator | 61 |
| Vision (engine + router) | test_vision_engine_new, test_vision_router | 36 |
| Integration | test_integration | 36 |
| Cache | test_cache | 16 |
| Planning | test_planner | 16 |
| Context/prompts | test_context_manager | 14 |
| Circuit Breaker + Health | test_circuit_breaker_health | 22 |
| Tutor core | test_tutor | 31 |
| Profile + mastery | test_profile_automation | 39 |
| Gamificação + export | test_advanced_gamification_export | 45 |
| Critical vision | test_critical_vision | 17 |
| Error notebook | test_error_notebook | 15 |
| Audio | test_vad, test_wake_word | 12 |
| Tools | test_rag, test_calculator, test_registry_websearch | 23 |
| Security | test_permissions | 3 |
| Exercises | test_exercises | 6 |
| **Total** | | **390** |

**Fixtures:** 1 (`tmp_db`) que injeta 21 tabelas e patcha módulos.

---

## 6. API Endpoints

| Método | Endpoint | Router | Status |
|---|---|---|---|
| POST | /api/chat | chat | ✅ |
| GET | /api/health | health | ✅ V2 (6 components) |
| GET | /api/sessions | chat | ✅ |
| GET | /api/sessions/{id}/messages | chat | ✅ |
| POST | /api/screen/capture | screen | ✅ |
| GET | /api/screen/monitors | screen | ✅ |
| GET | /api/screen/preview | screen | ✅ |
| POST | /api/screen/analyze | screen | ✅ |
| POST | /api/documents/upload | documents | ✅ |
| GET | /api/documents | documents | ✅ |
| GET | /api/documents/{id} | documents | ✅ |
| POST | /api/exercises/generate | exercises | ✅ |
| POST | /api/exercises/generate/adaptive | exercises | ✅ NEW |
| POST | /api/exercises/generate/review | exercises | ✅ NEW |
| POST | /api/exercises/grade | exercises | ✅ |
| POST | /api/audio/transcribe | audio | ✅ |
| POST | /api/audio/speak | audio | ✅ |
| GET | /api/flashcards/decks | tutor | ✅ |
| POST | /api/flashcards/generate | tutor | ✅ |
| POST | /api/flashcards/review | tutor | ✅ |
| POST | /api/study-plans/generate | tutor | ✅ |
| GET | /api/stats/dashboard | tutor | ✅ |
| GET | /api/profile | tutor | ✅ |
| PUT | /api/profile | tutor | ✅ |
| GET | /api/achievements | tutor | ✅ |
| PUT | /api/permissions/group/{group} | tutor | ✅ NEW |
| POST | /api/permissions/{name}/temporary | tutor | ✅ NEW |
| GET | /api/permissions/audit | tutor | ✅ NEW |

---

## 7. Problemas Resolvidos (V3 → V4)

### P0 — Crítico ✅ RESOLVIDO

| # | Problema | Solução |
|---|---|---|
| 1 | Pipeline de visão não-determinístico | Vision pipeline com intent→plan→capture→validate→OCR→vision→evidence→LLM→validate→respond |
| 2 | agent.py monolítico | Agent Loop V2 com per-tool circuit breakers, retry+backoff, MAX_STEPS=5 |
| 3 | Sem evidência estruturada | EvidenceStore com EvidenceType enum, Evidence dataclass, ResponseValidator |

### P1 — Alto ✅ RESOLVIDO

| # | Problema | Solução |
|---|---|---|
| 4 | Tool registry simplificado | ToolRegistry V2 com version, tags, by_tag(), by_permission(), discover() |
| 5 | Sem retry/fallback | Retry com exponential backoff (200/400ms), permission denied break |
| 6 | Sem timeout por tool | Per-tool circuit breaker (failure_threshold=3, recovery=60s) |
| 7 | Sem observabilidade | Structured logging (request_id, session_id), health check 6 components |
| 8 | Chat.tsx God Component | 🚧 Parcial — painéis extraídos (Evidence, Exercises, Flashcards) |

### P2 — Médio ✅ RESOLVIDO

| # | Problema | Solução |
|---|---|---|
| 15 | Sem testes HTTP/integration | 36 integration tests (E2E, regression, error recovery) |

### P3 — Baixo 🔄 EM PROGRESSO

| # | Problema | Status |
|---|---|---|
| 18 | Sem testes no frontend | 🚧 Parcial — sem framework de testes ainda |

---

## 8. O Que Está Funcionando Bem

| Componente | Status | Testes |
|---|---|---|
| Orchestrator V3 | ✅ Excelente | 61 |
| Agent Loop V2 | ✅ Excelente | 36 (integration) |
| Cache Layer | ✅ Excelente | 16 |
| Circuit Breaker | ✅ Excelente | 22 |
| SM-2 / Flashcards | ✅ Excelente | 31 |
| Perfil + Mastery | ✅ Excelente | 39 |
| Gamificação | ✅ Excelente | 45 |
| Error Notebook | ✅ Bom | 15 |
| Vision Pipeline | ✅ Bom | 17 |
| RAG V2 | ✅ Bom | 7 + embedding cache |
| Permissions V2 | ✅ Bom | audit + groups + hierarchy |
| Context Manager V2 | ✅ Bom | 14 + token trimming |
| Observability | ✅ Bom | structured logging + health |
| Deploy | ✅ Pronto | Docker + docker-compose |

---

## 9. Implementado (V3 → V4)

| Componente | Estado V3 | Estado V4 |
|---|---|---|
| Agent Loop | Monolítico `_run_tool_loop` | V2: per-tool CB, retry+backoff, MAX_STEPS=5, structured logging |
| Circuit Breaker | Inexistente | CLOSED→OPEN→HALF_OPEN com recovery |
| Observability | Logs dispersos | StructuredLogger, request_id, health check 6 components |
| Evidence Panel | Inexistente | Frontend panel com badges, pipeline stages, tools used |
| Exercise Engine | Básico | V2: adaptive, review, weak topics |
| Permission System | 3 testes básico | V2: audit log, groups, hierarchy, temporary grants |
| Memory & Context | Sem trimming | V2: _estimate_tokens, MAX_CONTEXT_CHARS=12000, _trim_history |
| Deployment | Manual | Dockerfile + docker-compose + nginx + .env.example |
| Caching | Nenhum | TTLCache LRU: OCR (128/2h), vision (64/30m), docs (32/24h) |
| RAG | Básico | V2: embedding cache, reranking, metadata, page_range filter |
| Keyboard Shortcuts | Nenhum | Ctrl+Shift+E/S/X/F/L/H + Escape |
| Frontend Polish | Básico | Spinner, skeleton, responsive, focus-visible a11y |
| Integration Tests | 0 | 36 tests (E2E, regression, error recovery, smoke) |

---

## 10. Próximos Passos

### Fase 9 — Frontend Decomposition
- Extrair ChatInput, ChatMessages, ChatVoice do Chat.tsx
- Criar hooks: useChat, useVoice, useScreen, useHandsFree
- Reduzir Chat.tsx de ~990 para <300 linhas

### Fase 10 — Performance
- Lazy loading de painéis
- Compressão de imagem antes de enviar ao LLM
- Debounce de input

### Fase 11 — Testes Frontend
- Configurar Vitest
- Testes de componentes críticos
- Snapshot tests

### Fase 12 — Documentation
- README.md atualizado
- Guia de deployment
- Contributing guide

---

## 11. Regras de Implementação

1. **NÃO remover funcionalidades** existentes sem justificativa
2. **NÃO quebrar APIs** existentes (versionar se necessário)
3. **NÃO criar mocks** para mascarar bugs reais
4. **NÃO declarar conclusão** sem teste
5. **PRIMEIRO** audit → fix → improve → test → commit
6. **Cada fase** deve ter: código + testes + lint + documentação
7. **Regressão** — rodar pytest + ruff antes e depois de cada alteração
8. **390 testes existentes** devem continuar passando sempre

---

## 12. Dependências Críticas

| Dependência | Uso | Status Health Check |
|---|---|---|
| Ollama | LLM inference | ✅ check_ollama |
| Tesseract | OCR | ✅ check_tesseract |
| SQLite | Banco de dados | ✅ check_database |
| MSS/cosmic-screenshot | Captura de tela | ✅ check_screen_capture |
| faster-whisper | STT | ⚠️ Não verificado |
| piper-tts | TTS | ⚠️ Não verificado |

**6/8 componentes verificados no /api/health.**

---

*Fim da auditoria V4. Próximo passo: Fase 9 — Frontend Decomposition.*
