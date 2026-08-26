# StudyAgent — Architecture Audit V3

**Data:** 2026-08-26
**Commit:** fd20862
**239 testes passando | ruff clean | TypeScript strict**

---

## 1. Visão Geral do Projeto

| Componente | Stack | Status |
|---|---|---|
| Backend | Python 3.11+ / FastAPI / SQLite / Ollama | Funcional |
| Frontend | React 18 / TypeScript strict / Vite | Funcional |
| LLM | Ollama (llama3.1 text, qwen2.5vl:7b vision) | Funcional |
| OCR | Tesseract via subprocess | Funcional |
| STT | faster-whisper | Funcional |
| TTS | piper-tts | Funcional |
| Captura | MSS + cosmic-screenshot (Wayland) | Funcional |
| RAG | NumPy embeddings + cosine similarity | Funcional |

---

## 2. Arquitetura Atual

```
routers/ ──> agent/ ──> core/ ──> vision/
                         tools/  ──> db
                         tutor/
                  │
                  v
              security/
```

### Camadas

| Camada | Responsabilidade | Arquivos |
|---|---|---|
| **routers/** | HTTP endpoints (6 routers) | chat, screen, documents, exercises, audio, tutor |
| **agent/** | Orquestração, loop de ferramentas, memória | agent.py, llm.py, memory.py, exercises.py |
| **core/** | Planejamento, contexto, modelos, registro de tools | planner.py, context_manager.py, model_manager.py, vision_router.py, tool_registry.py, registered_tools.py |
| **vision/** | Captura, OCR, janela, processamento | screen.py, ocr.py, window.py, engine.py |
| **audio/** | STT, TTS, VAD, wake word, listener | 5 módulos |
| **tools/** | Calculadora, RAG, documentos, web search | 4 módulos |
| **tutor/** | Flashcards, planos, perfil, gamificação, erros | 8 módulos |
| **security/** | Permissões | permissions.py |

### Dependências (sem ciclos)

```
routers → agent, core, vision, tools, tutor, security
agent   → core, vision, tools, security
core    → tools (registered_tools), vision (vision_router)
vision  → core (vision_router)
tools   → db
tutor   → db
security → (nada interno)
audio   → config
```

**Resultado: NENHUM import circular.**

---

## 3. Inventário de Arquivos

### Backend (43 arquivos .py)

| Módulo | Arquivos | Linhas estimadas |
|---|---|---|
| app/ | __init__, main, config, db | ~200 |
| agent/ | agent, llm, memory, exercises | ~700 |
| core/ | planner, context_manager, model_manager, vision_router, tool_registry, registered_tools | ~900 |
| vision/ | screen, ocr, window, engine | ~400 |
| audio/ | listener, speech_to_text, text_to_speech, vad, wake_word | ~600 |
| tools/ | calculator, documents, rag, web_search | ~500 |
| tutor/ | flashcards, study_plan, profile, stats, gamification, advanced_profile, automation, error_notebook, export_import | ~1200 |
| security/ | permissions | ~80 |
| **Total** | **43** | **~4600** |

### Frontend (15 arquivos)

| Arquivo | Linhas | Função |
|---|---|---|
| api.ts | 662 | Cliente API + 20+ interfaces |
| App.tsx | 33 | Layout raiz |
| Chat.tsx | 902 | God component (chat + voz + câmera + tela + painéis) |
| AgentFace.tsx | 111 | Face animada SVG |
| Sidebar.tsx | 48 | Navegação |
| ExercisesPanel.tsx | 196 | Exercícios |
| FlashcardsPanel.tsx | 270 | Flashcards + SM-2 |
| StudyPlanPanel.tsx | 182 | Planos de estudo |
| StatsPanel.tsx | 242 | Dashboard |
| ProfilePanel.tsx | 117 | Perfil |
| AchievementsPanel.tsx | 95 | Gamificação |
| PermissionsPanel.tsx | 35 | Permissões |
| ActionConfirm.tsx | 60 | Ações pendentes |
| PdfViewer.tsx | 151 | Leitor PDF + audiobook |
| index.css | 1113 | Estilos globais |

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

## 5. Testes (239)

| Área | Arquivo | Testes |
|---|---|---|
| Vision (engine + router) | test_vision_engine_new, test_vision_router | 36 |
| Planning | test_planner | 16 |
| Context/prompts | test_context_manager | 14 |
| Tutor core | test_tutor | 31 |
| Profile + mastery | test_profile_automation | 39 |
| Gamificação + export | test_advanced_gamification_export | 45 |
| Error notebook | test_error_notebook | 15 |
| Audio | test_vad, test_wake_word | 12 |
| Tools | test_rag, test_calculator, test_registry_websearch | 23 |
| Security | test_permissions | 3 |
| Exercises | test_exercises | 6 |

**Fixtures:** 1 (`tmp_db`) que injeta 20 tabelas e patcha 11 módulos.

---

## 6. API Endpoints (existentes)

| Método | Endpoint | Router |
|---|---|---|
| POST | /api/chat | chat |
| GET | /api/health | chat |
| GET | /api/sessions | chat |
| GET | /api/sessions/{id}/messages | chat |
| POST | /api/screen/capture | screen |
| GET | /api/screen/monitors | screen |
| GET | /api/screen/preview | screen |
| POST | /api/screen/analyze | screen |
| POST | /api/documents/upload | documents |
| GET | /api/documents | documents |
| GET | /api/documents/{id} | documents |
| POST | /api/exercises/generate | exercises |
| POST | /api/exercises/grade | exercises |
| POST | /api/audio/transcribe | audio |
| POST | /api/audio/speak | audio |
| GET | /api/flashcards/decks | tutor |
| POST | /api/flashcards/generate | tutor |
| POST | /api/flashcards/review | tutor |
| POST | /api/study-plans/generate | tutor |
| GET | /api/stats/dashboard | tutor |
| GET | /api/profile | tutor |
| GET | /api/achievements | tutor |
| ... | (25+ endpoints tutor) | tutor |

---

## 7. Problemas Identificados

### P0 — Crítico

| # | Problema | Impacto |
|---|---|---|
| 1 | **Pipeline de visão não é determinístico** — "leia o monitor 2" pode retornar "Olá" | Usuário não consegue usar percepção de tela |
| 2 | **agent.py concentra demais responsabilidade** — planner, captura, OCR, visão, tools, resposta, tudo num único método `process()` | Impossível testar, debugar ou extender individualmente |
| 3 | **Sem evidência estruturada** — o resultado do OCR/visão é passado como string solta, não como objeto rastreável | Não há como validar se a resposta baseia-se em evidência real |

### P1 — Alto

| # | Problema | Impacto |
|---|---|---|
| 4 | **Tool registry simplificado** — tools não têm schema de entrada/saída, timeout, retry, permissão centralizada | Ferramentas falham silenciosamente |
| 5 | **Sem retry/fallback** — se captura falha, não tenta novamente | Sensação de instabilidade |
| 6 | **Sem timeout por ferramenta** — uma tool lenta bloqueia todo o agente | UX travada |
| 7 | **Sem observabilidade** — logs dispersos, sem execution_id, sem métricas | Impossível diagnosticar em produção |
| 8 | **Chat.tsx é God Component** — 902 linhas, 28 states, 15 refs | Manutenção impossível |

### P2 — Médio

| # | Problema | Impacto |
|---|---|---|
| 9 | **6 bare `except Exception:`** sem variável — descartam traceback | Erros ficam invisíveis |
| 10 | **3 print() em listener.py** em vez de logger | Inconsistência |
| 11 | **slowapi não está no requirements.txt** | Deploy pode falhar |
| 12 | **URL do backend hardcoded** no frontend (`localhost:8000`) | Não funciona em outros hosts |
| 13 | **5 funções sem return type** em api.ts | TypeScript any implícito |
| 14 | **15 catch vazios** no frontend | Erros silenciados |
| 15 | **Sem testes HTTP/integration** — apenas unitários | Router bugs passam despercebidos |

### P3 — Baixo

| # | Problema | Impacto |
|---|---|---|
| 16 | **Sem ESLint/Prettier** no frontend | Formatação inconsistente |
| 17 | **Sem code splitting** no frontend | Bundle monolítico |
| 18 | **Sem testes no frontend** | Regressão visual possível |
| 19 | **config.py cria diretórios no import** | Side effect surpresa em testes |

---

## 8. O Que Está Funcionando Bem

| Componente | Status | Notas |
|---|---|---|
| SM-2 / Flashcards | ✅ Excelente | 31 testes, algoritmo correto |
| Perfil + Mastery | ✅ Excelente | 39 testes, scoring adaptativo |
| Gamificação | ✅ Excelente | 45 testes, XP/conquistas/streaks |
| Error Notebook | ✅ Bom | 15 testes, pipeline error→flashcard |
| Calculadora AST | ✅ Segura | 5 testes, sem eval() |
| RAG | ✅ Funcional | 7 testes, embeddings locais |
| Permissions | ✅ Funcional | 3 testes, persistência JSON |
| Wake Word | ✅ Funcional | 7 testes, normalização PT-BR |
| VAD | ✅ Funcional | 5 testes, detecção por energia |
| Export/Import | ✅ Funcional | CSV + JSON |
| PDF + Audiobook | ✅ Funcional | Extração + TTS |
| Context Manager | ✅ Bom | 14 testes, resumo rolante |

---

## 9. O Que Precisa de Evolução

| Componente | Estado Atual | Estado Desejado |
|---|---|---|
| Agent Orchestrator | agent.py monolítico | Módulo `core/orchestrator/` com execution plan, context, executor, validator, evidence |
| Vision Pipeline | Captura funciona, mas resposta é não-determinística | Pipeline completo: intent→plan→capture→validate→OCR→vision→evidence→LLM→validate→respond |
| Tool Registry | Simples (name, fn, permission) | Profissional (schema, timeout, retry, category, dangerous, version) |
| Evidence Store | Inexistente | Objeto rastreável por execução com source, type, content, confidence |
| Response Guard | Inexistente | Validação pós-LLM: pergunta respondida? evidência existe? alucinação? |
| Observability | Logs dispersos | Structured logging com execution_id, métricas, timing |
| Frontend State | God component | Decomposição + execution timeline + estados visuais |
| Error Hierarchy | Exception genérica | ToolError, VisionError, CaptureError, etc. |
| Retry/Fallback | Inexistente | Políticas por tool com max retries e fallback chains |
| Cache | Nenhum | OCR cache, vision cache, document cache |

---

## 10. Plano de Migração

### Fase 1 — Diagnóstico ✅ (este documento)

### Fase 2 — Vision Pipeline Definitivo
- Corrigir `analyze_screen()` → fluxo `use_screen=True`
- Garantir monitor correto chega ao Ollama
- Adicionar validação de imagem antes de enviar ao modelo
- Teste crítico: "leia o monitor 2" → resposta descreve conteúdo

### Fase 3 — Orchestrator Core
- Criar `core/orchestrator/`:
  - `execution_plan.py` (ExecutionStep, ExecutionPlan)
  - `execution_context.py` (contexto compartilhado)
  - `executor.py` (executa steps com retry/timeout)
  - `evidence.py` (EvidenceStore)
  - `validator.py` (valida evidência e resposta)
  - `policies.py` (retry, timeout, fallback)
  - `errors.py` (hierarquia de erros)
  - `orchestrator.py` (orquestra tudo)

### Fase 4 — Tool Registry V2
- Schema de entrada/saída por tool
- Timeout e retry configuráveis
- Contrato de resultado estruturado
- Categorias: screen, vision, document, web, audio, tutor

### Fase 5 — Agent Loop V2
- UNDERSTAND → PLAN → EXECUTE → OBSERVE → VALIDATE → SYNTHESIZE → RESPOND
- Substituir `_run_tool_loop` monolítico
- Limitar iterações
- Suporte a replanning

### Fase 6 — Observability
- Structured logging com execution_id
- Métricas por tool (latência, retries, falhas)
- Health check completo (/api/health com todos os subsistemas)

### Fase 7 — Frontend Evolution
- Decompor Chat.tsx
- Adicionar execution timeline
- Estados visuais do agente
- Debug panel opcional

### Fase 8 — Hardening
- Timeouts por tool
- Fallback chains
- Error hierarchy completa
- Cache (OCR, vision, documentos)
- Testes de regressão end-to-end

---

## 11. Regras de Implementação

1. **NÃO remover funcionalidades** existentes sem justificativa
2. **NÃO quebrar APIs** existentes (versionar se necessário)
3. **NÃO criar mocks** para mascarar bugs reais
4. **NÃO declarar conclusão** sem teste
5. **PRIMEIRO** audit → fix → improve → test → commit
6. **Cada fase** deve ter: código + testes + lint + documentação
7. **Regressão** — rodar pytest + ruff antes e depois de cada alteração
8. **239 testes existentes** devem continuar passando sempre

---

## 12. Dependências Críticas

| Dependência | Uso | Risco |
|---|---|---|
| Ollama | LLM inference | Se indisponível, toda resposta falha |
| Tesseract | OCR | Se indisponível, visão de texto falha |
| MSS | Captura de tela | Funciona em X11; Wayland usa cosmic-screenshot |
| cosmic-screenshot | Captura Wayland | Pode não estar instalado |
| faster-whisper | STT | Se indisponível, voz não funciona |
| piper-tts | TTS | Se indisponível, leitura não funciona |

**Todos devem ser verificados no /api/health.**

---

*Fim do diagnóstico. Próximo passo: Fase 2 — Vision Pipeline Definitivo.*
