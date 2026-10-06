# StudyAgent

Tutor de estudos multimodal que roda **100% local** no seu computador (Linux): chat com IA local via Ollama com **resposta em streaming (SSE)**, voz nos dois sentidos, visão computacional para ler telas e câmera com **reconhecimento facial**, leitura completa de PDFs, pesquisa na internet com fontes citadas, exercícios com correção automática, flashcards com repetição espaçada, planos de estudo, perfil adaptativo, gamificação com XP e níveis, recomendações por tempo, export/import em CSV e JSON, avatar 3D reativo e ferramentas de edição de código — tudo sob um sistema de permissões explícitas.

## Funcionalidades

### 💬 Conversa com tutor de IA
- **Resposta em streaming (SSE)**: tokens chegam em tempo real via `POST /api/chat/stream` (com fallback síncrono em `/api/chat`)
- Modelos locais via Ollama (`llama3.1` texto, `qwen2.5vl:7b` visão) — nada sai do computador
- **Metodologia socrática**: modo tutor (padrão) guia com perguntas antes de dar respostas
- Persona configurável: professor, tutor (socrático), exercícios, revisão, resumo, simples
- **Dashboard do aluno**: agente tem acesso a pontos fracos, fortes, atividade recente e streak
- **Consciência contextual**: referências a exercícios anteriores, temas fracos, tela mostrada
- Memória rolante: últimas mensagens + resumo automático da sessão
- Calculadora segura embutida
- **Ferramentas de código**: o agente pode ler (`read_code`), criar (`write_code`), editar (`edit_code`) e buscar em arquivos (`list_files`, `search_code`) — sempre sob a permissão explícita de acesso a arquivos

### 🗣 Voz completa
- **Modo viva-voz opcional**: diga **"ei Study, sua pergunta"** em qualquer aba/janela — o agente ouve pela palavra de acordar, responde no chat e fala a resposta pelos alto-falantes
- **🎧 Audiobook de documentos**: no leitor de PDF, toque em 🎧 para ouvir o arquivo página por página (acessibilidade)
- **Fala → texto:** faster-whisper com VAD silero, prompt PT-BR, beam greedy por padrão (`STUDY_STT_BEAM=1`) para transcrição rápida na CPU — modelos pré-carregados no startup do backend
- **Pontuação inteligente:** a transcrição sai com maiúscula inicial e pontuação correta — `?` quando há palavra interrogativa **ou** quando a entonação do áudio sobe no fim (pergunta de "sim/não" como *"vamos fazer um novo teste?"*)
- **Modo conversa automática 🔄:** o agente ouve continuamente (VAD no navegador), transcreve, responde e fala — mão livre, com meio-duplex (só a fala do agente bloqueia o microfone; durante o raciocínio ele já volta a ouvir)
- **Texto → fala:** Piper com voz brasileira `pt_BR-faber-medium`

### 👀 Visão
- 🖥 Anexo captura de tela à mensagem
- 📺 Painel *ao vivo* multi-monitor com atualização contínua e **modo comentarista** (o agente avisa quando algo muda na tela)
- 📷 Câmera: aponte, capture e pergunte
- 👤 **Reconhecimento facial (InsightFace)**: cadastre rostos (`/api/face/register`), detecte quem está na frente da câmera (`/api/face/present`) e personalize o atendimento (`/api/face/recognize`)
- Visão por IA híbrida: OCR Tesseract + leitura do modelo de visão

### 📄 Documentos
- Upload de PDF/txt/md com extração de texto
- **Leitura integral (map-reduce):** resumo completo do documento inteiro, cache por arquivo
- **RAG semântico:** busca por embeddings `nomic-embed-text` + numpy cosine similarity, Índices persistentes em `.npz`
- **Leitor integrado:** visualize o PDF dentro do app enquanto conversa sobre ele
- Documento anexado tem prioridade sobre captura de tela

### 🌐 Pesquisa na internet (com honestidade)
- Cascata de buscadores: DuckDuckGo → Bing → Wikipédia
- Abre automaticamente as páginas mais relevantes, extrai e destila os fatos objetivos
- Síntese final com o modelo de visão + regras de desambiguação
- Sempre cita fontes `[fonte: URL]`; se não achar, admite que não sabe

### 🎯 Exercícios
- Gera questões do tema que você escolher (múltipla escolha ou dissertativas)
- Gabarito fica no servidor — correção automática aceitando respostas equivalentes (`0,5` = `1/2`)
- **Histórico persistente:** resultados salvos automaticamente para o dashboard de progresso
- **Scoring ponderado**: dificuldade, consistência, recência e volume alimentam o mastery score
- **Caderno de erros automático**: questões erradas são salvas para revisão futura
- **XP automático**: cada exercício completo dá XP baseado em dificuldade e desempenho

### 🃏 Flashcards com repetição espaçada
- Geração automática de flashcards via LLM a partir de um tema
- Algoritmo SM-2 (mesmo do Anki): intervalo cresce conforme você acerta, recomeça quando erra
- Revisão interativa: revele a resposta e avalie (😵 de novo / 😓 difícil / 😊 bom / 🤩 fácil)
- Stats por deck: total, pendentes, dominados (intervalo > 21 dias)
- **Pipeline exercício→flashcard**: gere flashcards automaticamente a partir do caderno de erros
- **XP por revisão**: 5 XP (acertou) ou 2 XP (errou) por card revisado

### 📋 Planos de estudo
- Geração automática de planos estruturados via LLM (5-12 subtópicos)
- Checklist interativo com barra de progresso
- Progresso salvo no SQLite — retome de onde parou
- **Mastery-aware**: planos usam dados de mastery e erros recentes para focar nos pontos fracos
- **XP por conclusão**: 50 XP ao completar um plano 100%

### 📝 Caderno de erros
- Erros de exercícios são salvos automaticamente (pergunta, resposta errada, resposta correta, explicação)
- Filtrar por tema, marcar como revisado, ver estatísticas
- **Pipeline exercício→flashcard**: gere flashcards diretamente dos erros pendentes

### 📊 Dashboard de progresso
- Grid de métricas: exercícios feitos, média geral, streak de dias, flashcards dominados, % planos
- **Mastery por tema**: barras coloridas (vermelho/amarelo/verde) com percentual
- **Resumo semanal**: exercícios 7d, média 7d, tempo estudado, temas praticados
- **Caderno de erros**: total de erros pendentes, temas com mais erros
- **Analytics temporal**: horários mais produtivos, tempo médio por sessão
- **Recomendações por tempo**: "Tenho 30 minutos" → sugere o que estudar
- Alertas quando há cards pendentes de revisão

### 🎮 Gamificação com XP e Níveis
- **Sistema de XP**: ganhe XP por exercícios (5-37 XP), flashcards (2-5 XP), streaks (10-30 XP), planos (50 XP)
- **5 níveis progressivos**:
  - 🌱 Iniciante (0 XP)
  - 📖 Estudante (100 XP)
  - 🎓 Graduado (300 XP)
  - ⚡ Especialista (600 XP)
  - 👑 Mestre (1000 XP)
- **26 conquistas desbloqueáveis**: streaks, domínio, planos, temas, níveis
- **Leaderboard**: XP total, XP semanal, conquistas, streak, temas dominados
- **Barra de nível** no dashboard com progresso e XP para próximo nível
- Verificação automática de conquistas ao interagir com exercícios, flashcards e planos

### 👤 Perfil adaptativo do aluno
- Cadastro: nome, série, escola, preferências
- **Domínio por tema:** tracking automático com **weighted scoring** (30% dificuldade, 25% consistência, 25% recência, 20% volume)
- **Rolling window real:** janela de 5 resultados recentes com evict de dados antigos
- **Detecção de pontos fracos:** temas com weighted score < 55% são sinalizados
- O agente recebe os pontos fracos no system prompt e prioriza esses temas

### ⚡ Automação com confirmação
- Quando o agente quer executar uma ação (gerar exercícios, criar plano, pesquisar), propõe formalmente
- Barra flutuante com botões ✓ executar / ✕ recusar
- Histórico de propostas aprovadas/rejeitadas

### ⏱ Perfil avançado
- Registro de sessões de estudo com duração (exercício, revisão, chat)
- **Analytics temporal**: horários mais produtivos, média de tempo por sessão
- **Dificuldade adaptativa**: rolling window real de 5 resultados ajusta nível automaticamente
- **Recomendações por tempo**: "Tenho 30 minutos" → sugere o que estudar (usa weighted score)

### 📤 Export/Import
- **Flashcards**: exportar baralho em CSV (compatível com Anki) ou JSON
- **Importar**: cole um CSV front/back ou importe um JSON exportado
- **Planos de estudo**: exportar como JSON
- **Perfil completo**: exportar/importar todos os dados (perfil, mastery, decks, planos)

### 🔒 Segurança
- **Rate limiting**: chat 15/min, exercícios 5/min e correção 30/min (slowapi) + flashcards 10/min, planos 10/min, áudio 20-30/min e reconhecimento facial 10-30/min
- **Permissões explícitas**: nenhum módulo acessa microfone, câmera, tela, arquivos ou internet sem checar
- **Ferramentas de código**: ler/criar/editar/buscar arquivos usa permissão `filesystem` (`file_access` default ativo) — controlável pelo painel de permissões
- **PIN local (`STUDYAGENT_PIN`)**: ativar permissões perigosas (controle do mouse/teclado, execução de comandos) exige o PIN no header `X-StudyAgent-Pin` — impedindo que uma página/processo local malicioso conceda controle total sem consentimento
- **Escuta só no localhost**: a API faz bind em `127.0.0.1` (start.sh, install.sh, systemd); o Docker publica a porta apenas no host (`127.0.0.1:8000`) e não na rede
- **Proteção CSV**: exportação de flashcards escapa células que começam com `=`, `+`, `-`, `@` (anti CSV injection) e nomes de arquivo são sanitizados no Content-Disposition
- **Global exception handler**: erros internos retornam 500 seguro sem vazar detalhes

### 🛠 Infraestrutura
- `install.sh` — instalação completa (Python, npm, Ollama, systemd)
- `doctor.sh` — verificação de saúde com cores (pass/warn/fail); `--quick` pula as seções de inferência real (~1 s vs ~16–75 s)
- `start.sh` / `stop.sh` — gerenciamento de serviços
- `update.sh` — git pull + backup automático
- `backup.sh` — backups comprimidos com rotação de 10

### 🎭 Interface
- **Avatar 3D reativo** (Three.js / React Three Fiber): pensa, ouve, grava, fala — com rostos realistas, partículas de fundo e olhos que seguem o cursor (estados em `agentStates`)
- **Modo palco:** avatar em tela cheia (⤢, Esc para sair)
- Layout **glassmorphism**: brilhos radiais, blur, acentos neon e animações de hover
- **Painel de evidências**: visualiza as etapas do pipeline do agente (ferramentas usadas, badges, estágios)
- **Painel de câmera** com captura e reconhecimento facial
- Sidebar de ferramentas sanfona (permissões aninhadas) e gerenciador de painéis
- Tema escuro, tudo em português

## Arquitetura

```
backend/app/
├── main.py                 FastAPI (8 routers + middleware request-id/timing + rate limiting + exception handler)
├── db.py                   Pool de conexões SQLite thread-safe (WAL mode) com recuperação
├── config.py               Caminhos, modelos Ollama
├── core/                   Núcleo V2 (desacoplado do agente)
│   ├── orchestrator/         Plan builder → executor com circuit breaker, evidence, policies, validator
│   ├── model_manager.py      Papéis de modelos por env (text/vision/synthesis/embedding/stt/tts)
│   ├── planner.py            Decide captura de tela, monitor e estratégia de documento
│   ├── plan_builder.py       Constrói planos de execução com as ferramentas registradas
│   ├── context_manager.py    System prompt socrático + dashboard do aluno + propostas
│   ├── vision_router.py      Notas de imagem, bloco híbrido de OCR, janela ativa
│   ├── tool_registry.py      Registro decorado de ferramentas + schemas p/ tool-calling
│   ├── registered_tools.py   web_search, open_url, calculate + 5 de código (permissão filesystem)
│   ├── structured_logging.py Logging estruturado com request_id/session_id
│   ├── memory_manager.py     Estimativa de tokens + trimming da janela de contexto
│   ├── health.py             Health check (6 componentes)
│   ├── vector_store.py       Stores de embeddings (numpy/chroma) para RAG
│   └── cache.py / fs_manager.py / env_validation.py
├── routers/                chat, screen, exercises, documents, audio (+audio_stream), tutor, facial, health
├── agent/
│   ├── agent.py            Orquestrador: plano → ferramentas → resposta (síncrona ou SSE stream)
│   ├── llm.py              Cliente Ollama + síntese de pesquisas (qwen2.5vl)
│   ├── memory.py           SQLite: 21 tabelas
│   └── exercises.py         Gerador + corretor + grade_and_track (atualiza mastery + XP)
├── tutor/                  Módulos de tutoria (P5-P10 + Phase 3 adaptive)
│   ├── flashcards.py         SM-2, geração LLM, review, stats por deck, XP
│   ├── study_plan.py         Planos LLM mastery-aware + checklist toggle + progresso
│   ├── stats.py              Dashboard combinado + enhanced dashboard + mastery by subject
│   ├── profile.py            Perfil + weighted scoring + student_dashboard() para system prompt
│   ├── automation.py         Propostas de ação, approve/reject, prompt injetado
│   ├── advanced_profile.py   Sessões, analytics, rolling window real, recomendações ponderadas
│   ├── gamification.py       26 conquistas, XP, 5 níveis, leaderboard, streaks por tema
│   ├── error_notebook.py     Caderno de erros + pipeline exercício→flashcard
│   └── export_import.py      CSV/Anki flashcards, JSON planos, perfil completo
├── vision/
│   ├── screen.py           Captura multi-monitor (mss + cosmic-screenshot p/ Wayland)
│   ├── window.py           Janela ativa (xdotool/swaymsg)
│   ├── engine.py           Pipeline de visão (screentext/detalhes/objeto)
│   ├── ocr.py              OCR Tesseract (híbrido com a visão do modelo)
│   └── facial.py           Reconhecimento facial (InsightFace)
├── audio/
│   ├── speech_to_text.py   faster-whisper com VAD silero + prompt PT-BR (+ anti-alucinação)
│   ├── text_to_speech.py   Piper TTS
│   ├── vad.py              Segmentador por energia (puro numpy, testável)
│   ├── wake_word.py        Gatilho "ei study" sobre a transcrição STT
│   ├── intonation.py       Detecção de entonação de pergunta (F0/autocorrelação, sem modelo)
│   ├── orthography.py       Normalização PT-BR pós-STT (maiúscula, "?", formas faladas)
│   ├── listener.py         Daemon viva-voz (arecord→VAD→STT→chat→TTS→aplay), meio-duplex
│   └── voice_streamer.py   Streaming de resposta em áudio (tokens → fala)
├── tools/
│   ├── calculator.py       Avaliador AST seguro
│   ├── code_editor.py      Leitura/escrita/edição/busca de arquivos (permissão filesystem)
│   ├── documents.py        Extração PDF, digest map-reduce, narração (audiobook)
│   ├── rag.py              Busca semântica (embeddings + cosine)
│   └── web_search.py       DDG→Bing→Wikipédia, fetch, destilação
└── security/
    ├── permissions.py      Portão de permissões (fail-closed + dependências + auditoria)
    └── local_auth.py       PIN local (STUDYAGENT_PIN + X-StudyAgent-Pin) p/ permissões perigosas

frontend/src/
├── App.tsx                 Layout glassmorphism: sidebar (com permissões) + chat
├── api.ts                  Cliente tipado (50+ funções)
├── components/
│   ├── Chat.tsx              Núcleo da UI (conversa, voz, telas, câmera, sidebar)
│   ├── ChatMessages.tsx      Lista de mensagens + estado vazio/loading/error
│   ├── ChatInput.tsx         Campo de entrada + botões de ação
│   ├── LivePanel.tsx         Painel ao vivo multi-monitor
│   ├── StudyAgent3D/         Avatar 3D reativo (rostos, partículas, olhos, estados)
│   ├── EvidencePanel.tsx     Visualização das etapas do pipeline do agente
│   ├── CameraPanel.tsx       Câmera + reconhecimento facial
│   ├── Sidebar.tsx           Ferramentas sanfona + permissões aninhadas
│   ├── PanelManager.tsx      Gerenciador de painéis
│   ├── panels.ts             Definição/registro dos painéis
│   ├── ExercisesPanel.tsx    Quiz com correção
│   ├── FlashcardsPanel.tsx   Baralhos + revisão SM-2 interativa
│   ├── StudyPlanPanel.tsx    Checklist de plano de estudo
│   ├── StatsPanel.tsx        Dashboard avançado + nível/XP + mastery bars
│   ├── ProfilePanel.tsx      Perfil + análise de aprendizado
│   ├── AchievementsPanel.tsx Conquistas + streaks por tema
│   ├── ActionConfirm.tsx     Barra de confirmação de ações
│   ├── PdfViewer.tsx         Leitor de documentos + 🎧 audiobook
│   └── PermissionsPanel.tsx
├── hooks/
│   ├── useChat.ts            Lógica de chat + envio (streaming/síncrono)
│   ├── useVoice.ts           Gravação + transcrição + fala
│   ├── useScreen.ts          Captura + monitores
│   ├── useAgentState.ts      Estado do avatar 3D
│   └── useDebounce.ts        Debounce de input
├── store/
│   └── userStore.ts        Estado global do usuário
├── lib/
│   └── audioReactive.ts    Reatividade do avatar ao áudio (mouth-sync)
└── test/
    ├── ChatMessages.test.tsx
    ├── snapshots.test.tsx  Snapshot tests
    └── useDebounce.test.ts
```

### Banco de Dados (21 tabelas)

| Tabela | Descrição |
|---|---|
| `sessions` | Sessões de conversa |
| `messages` | Mensagens do chat |
| `summaries` | Resumos de sessão |
| `documents` | Documentos indexados |
| `exercise_history` | Histórico de exercícios |
| `exercise_store` | Exercícios gerados (temp) |
| `flashcard_decks` | Baralhos de flashcards |
| `flashcards` | Cards individuais |
| `flashcard_reviews` | Reviews de cards |
| `study_plans` | Planos de estudo |
| `study_items` | Itens dos planos |
| `student_profile` | Perfil do aluno |
| `topic_mastery` | Mastery por tema (com weighted_score) |
| `topic_results` | Resultados individuais por tema |
| `action_proposals` | Propostas de automação |
| `session_log` | Log de sessões (duração, tipo) |
| `adaptive_difficulty` | Dificuldade adaptativa por tema |
| `achievements` | Conquistas desbloqueadas |
| `error_notebook` | Caderno de erros |
| `student_xp` | Histórico de XP ganho |
| `student_level` | Nível e XP total |

### Testes

555 testes (537 backend + 18 frontend):

## Novidades recentes (autenticação facial e visão ambiente)

- Autenticação facial obrigatória na inicialização: o StudyAgent usa a câmera para identificar o aluno antes de permitir o uso do agente. Isto garante que permissões sensíveis só são liberadas após confirmação da identidade.
- Permissões sensíveis (câmera e captura de tela) são liberadas apenas após reconhecimento bem-sucedido do usuário. Antes disso, essas permissões ficam desativadas por padrão.
- Integração visão ↔ memória: quando a visão (câmera ou captura de tela) confirma a presença de um objeto e o assistente descreve sua localização, o agente grava essa observação na memória de ambiente com maior confiança (campo `confidence` em `environment_objects`).
- Mapeamento semântico de áreas: o agente extrai automaticamente áreas semânticas (ex.: "mesa da direita", "prateleira", "gaveta") de frases do usuário ou de observações do assistente e salva como `area` no banco.

Essas mudanças melhoram a privacidade (não habilita câmera sem identificação) e aumentam a acurácia do inventário do ambiente ao combinar observações visuais com memória persistente.

```bash
# Backend
cd backend
.venv/bin/pytest tests/ -v       # 537 testes
.venv/bin/ruff check app tests

# Frontend
cd frontend
npx vitest run                   # 18 testes
npx tsc --noEmit
npx vite build
```

> O pytest gera artefatos em `config/permissions.json` e `config/permission_audit.json`
> durante os testes de permissões — restaure com `git checkout config` após rodar a suíte.

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `STUDY_TEXT_MODEL` | `llama3.1` | Modelo de texto principal |
| `STUDY_VISION_MODEL` | `qwen2.5vl:7b` | Modelo de visão |
| `STUDY_SYNTH_MODEL` | (herda texto) | Síntese de pesquisas |
| `STUDY_EMBEDDING_MODEL` | `nomic-embed-text` | Embeddings para RAG |
| `STUDY_NUM_PREDICT` | `2048` | Limite de tokens na resposta |
| `STUDY_VAD_THRESHOLD` | `500` | Sensibilidade do microfone (listener) |
| `STUDY_STT_MODEL` | `small` | Modelo faster-whisper (transcrição) |
| `STUDY_STT_BEAM` | `1` | Beam size do Whisper (1 = greedy/mais rápido; 5 = mais preciso, mais lento) |
| `STUDY_STT_DEVICE` | `cpu` | Device do Whisper (`cpu` ou `cuda`) |
| `STUDY_STT_COMPUTE` | `int8` | Precisão de inferência do Whisper |
| `STUDY_STT_INTONATION` | `1` | Detecta entonação de pergunta (subida de pitch no fim) para pontuar a transcrição |
| `STUDY_STT_NO_SPEECH` | `0.6` | Corte de segmentos sem fala (anti-alucinação do Whisper) |
| `STUDY_STT_LOGPROB` | `-1.0` | Corte de segmentos de baixa confiança |
| `STUDY_STT_COMPRESSION` | `2.4` | Corte de repetição em loop |
| `STUDY_STT_HALLUC_SILENCE` | `2.0` | Corta "alucinação" gerada no silêncio |
| `STUDY_AUDIO_TIMEOUT` | `5` | Timeout de leitura do microfone no viva-voz (s = encerra o ciclo) |
| `STUDY_TTS_TIMEOUT` | `120` | Timeout do playback no viva-voz (s) |
| `STUDY_CYCLE_SLEEP` | `0.5` | Pausa entre ciclos do viva-voz (s) |
| `OLLAMA_HOST` | `http://localhost:11434` | Host do Ollama |
| `STUDYAGENT_HOST` | `127.0.0.1` | Interface de rede da API (localhost) |
| `STUDYAGENT_PIN` | _(vazio)_ | PIN para ativar permissões perigosas (ver **Segurança**) |

> **Configurando o PIN:** gere um PIN forte com `openssl rand -hex 12` e adicione
> `STUDYAGENT_PIN=<valor>` ao arquivo `backend/.env` (ele não é commitado). Com o PIN
> definido, ativar permissões perigosas passa a exigir `X-StudyAgent-Pin` no header;
> sem PIN definido, essas permissões ficam bloqueadas (fail-closed, HTTP 401).

## Requisitos

- Linux (Pop!_OS testado, inclui Wayland/COSMIC)
- Python 3.12+, Node 22+
- Ollama com `llama3.1`, `qwen2.5vl:7b` e `nomic-embed-text`
- GPU recomendada (RTX 3060 12GB roda tudo)

## Instalação

O instalador **identifica o sistema operacional** automaticamente e baixa o projeto:

| Sistema | Como instalar |
|---|---|
| **Linux / macOS** | `bash -c "$(curl -fsSL https://raw.githubusercontent.com/ANTONIOALGMAR/StudyAgent/main/setup.sh)"` |
| **Windows (WSL/Ubuntu)** | configure o WSL (`wsl --install`) e rode o mesmo comando acima dentro do terminal WSL |
| **Windows nativo (PowerShell)** | `iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/ANTONIOALGMAR/StudyAgent/main/install.ps1'))` |

O `setup.sh` (Linux/macOS/WSL) e o `install.ps1` (Windows nativo) detectam o SO, fazem o download
do repositório do GitHub, instalam dependências (backend + frontend), baixam os modelos locais
do Ollama e iniciam os serviços — tudo automaticamente.

### Rápida (Linux/macOS/WSL)

```bash
git clone https://github.com/ANTONIOALGMAR/StudyAgent.git ~/StudyAgent
cd ~/StudyAgent
./install.sh
```

### Windows nativo (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

> No Windows, o script cria o backend/frontend, baixa o projeto (via `git` ou ZIP do GitHub)
> e inicia tudo. Tesseract OCR e Ollama são opcionais — instaláveis depois.

### Manual

```bash
git clone https://github.com/ANTONIOALGMAR/StudyAgent.git ~/StudyAgent
cd ~/StudyAgent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

Modelos:

```bash
ollama pull llama3.1
ollama pull qwen2.5vl:7b
ollama pull nomic-embed-text
```

Voz brasileira do Piper (não vai no repo por tamanho):

```bash
mkdir -p backend/models && cd backend/models
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json
```

OCR nativo (opcional):

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-por
```

## Executando

### Com scripts (recomendado)

```bash
./start.sh     # Inicia todos os serviços
./stop.sh      # Para todos os serviços
./doctor.sh    # Verificação de saúde (completa, com inferência real)
./doctor.sh --quick   # Verificação rápida (~1s, sem inferência)
./update.sh    # Atualiza do git + backup
./backup.sh    # Cria backup comprimido
```

### Com systemd

```bash
cp scripts/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now studyagent-ollama studyagent-api studyagent-web
```

### Manualmente

```bash
# terminal 1
ollama serve
# terminal 2
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
# terminal 3
cd frontend && npx vite --port 5173
```

Abra **http://localhost:5173**

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Status e modelos |
| POST | `/api/chat` | Conversa (rate limit: 15/min) |
| POST | `/api/chat/stream` | Conversa em streaming (SSE, token a token) |
| POST | `/api/screen/capture` | Captura + OCR |
| GET | `/api/screen/monitors` | Lista monitores |
| GET | `/api/screen/preview` | JPEG do monitor (painel ao vivo) |
| POST | `/api/screen/analyze` | Análise de tela pela IA |
| POST | `/api/audio/transcribe` | Áudio → texto (Whisper) |
| POST | `/api/audio/speak` | Texto → áudio WAV (Piper) |
| POST | `/api/calculate` | Calculadora segura |
| POST | `/api/documents/upload` | Upload pdf/txt/md |
| GET | `/api/documents/{id}/file` | Arquivo original (leitor) |
| GET | `/api/documents/{id}/audio/plan` | Plano do audiobook |
| GET | `/api/documents/{id}/audio?idx=N` | Áudio WAV da parte N |
| POST | `/api/exercises/generate` | Gera questões (rate limit: 5/min) |
| POST | `/api/exercises/grade` | Corrige + mastery + XP |
| GET | `/api/flashcards/decks` | Lista baralhos |
| GET | `/api/flashcards/decks/{id}/due` | Cards pendentes |
| GET | `/api/flashcards/decks/{id}/stats` | Stats do baralho |
| POST | `/api/flashcards/generate` | Gera baralho via LLM |
| POST | `/api/flashcards/review` | Review + XP |
| POST | `/api/flashcards/generate-from-errors` | Flashcards do caderno de erros |
| GET | `/api/study-plans` | Lista planos |
| POST | `/api/study-plans/generate` | Gera plano via LLM |
| GET | `/api/study-plans/{id}` | Plano com itens |
| POST | `/api/study-plans/items/{id}/toggle` | Marca/desmarca item |
| GET | `/api/stats/dashboard` | Dashboard combinado |
| GET | `/api/stats/dashboard/enhanced` | Dashboard + mastery + semanal + erros |
| GET | `/api/stats/weekly-summary` | Resumo dos últimos 7 dias |
| GET | `/api/stats/mastery-by-subject` | Mastery por tema |
| GET | `/api/stats/time-analytics` | Horários produtivos |
| GET | `/api/profile` | Perfil do aluno |
| POST | `/api/profile` | Salva perfil |
| GET | `/api/profile/insights` | Análise de pontos fracos/fortes |
| GET | `/api/mastery` | Domínio por tema |
| GET | `/api/mastery/{topic}` | Detalhe de um tema |
| POST | `/api/actions/propose` | Cria proposta |
| POST | `/api/actions/{id}/approve` | Aprova proposta |
| POST | `/api/actions/{id}/reject` | Rejeita proposta |
| GET | `/api/actions/pending` | Propostas pendentes |
| POST | `/api/sessions/start` | Inicia sessão |
| POST | `/api/sessions/{id}/end` | Encerra sessão |
| GET | `/api/recommendations/{minutes}` | O que estudar em X min |
| GET | `/api/level` | Nível e XP |
| GET | `/api/leaderboard` | Leaderboard completo |
| GET | `/api/achievements` | Lista conquistas |
| GET | `/api/achievements/progress` | Progresso das bloqueadas |
| GET | `/api/achievements/check` | Verifica novas conquistas |
| GET | `/api/streaks` | Sequências por tema |
| GET | `/api/errors` | Caderno de erros |
| GET | `/api/errors/stats` | Estatísticas de erros |
| POST | `/api/errors/{id}/review` | Marca erro como revisado |
| POST | `/api/errors/review-topic` | Marca todos os erros de um tema |
| GET | `/api/flashcards/decks/{id}/export/csv` | Export CSV |
| GET | `/api/flashcards/decks/{id}/export/json` | Export JSON |
| POST | `/api/flashcards/import` | Import CSV |
| POST | `/api/flashcards/import/json` | Import JSON |
| GET | `/api/study-plans/{id}/export` | Export plano JSON |
| GET | `/api/profile/export` | Export perfil completo |
| POST | `/api/profile/import` | Import perfil completo |
| GET | `/api/sessions` | Lista sessões |
| GET | `/api/sessions/{id}/messages` | Mensagens de uma sessão |
| POST | `/api/face/present` | Detecta rosto na imagem |
| POST | `/api/face/register` | Cadastra um rosto |
| POST | `/api/face/recognize` | Reconhece o rosto cadastrado |
| GET | `/api/face/list` | Lista rostos cadastrados |
| DELETE | `/api/face/{name}` | Remove um rosto |
| GET/PUT | `/api/permissions[/{name}]` | Permissões (ativar permissões perigosas requer PIN) |

## Roadmap

### Funcionalidades (P1-P10)
- [x] P1 — Agent Core: model manager, planner, context manager, tool registry
- [x] P2 — Visão computacional: vision router, OCR híbrido, multi-monitor, janela ativa
- [x] P3 — Áudio: VAD por energia, wake word, daemon viva-voz, STT turbinado
- [x] P4 — RAG: embeddings, chunking, busca semântica, índices persistentes
- [x] P5 — Tutor escolar: flashcards SM-2, planos de estudo, dashboard de progresso
- [x] P6 — Perfil adaptativo: student profile, topic mastery, weak/strong detection
- [x] P7 — Automação com confirmação: action proposals, approve/reject
- [x] P8 — Perfil avançado: sessões, analytics temporal, dificuldade adaptativa, recomendações
- [x] P9 — Gamificação: 26 conquistas, streaks por tema, verificação automática
- [x] P10 — Export/Import: CSV/Anki, JSON, perfil completo

### Evolution Phases (Master Prompt)
- [x] Phase 1 — Audit: full codebase analysis, bug inventory, architecture review
- [x] Phase 2 — Stability: centralized SQLite DB, CORS hardening, safe defaults, router split, thread-safe permissions
- [x] Phase 3 — Adaptive Motor: weighted scoring (difficulty/consistency/recency/volume), real rolling window, topic_results table
- [x] Phase 4 — Smart Tutor: Socratic methodology, student_dashboard(), dynamic state injection, contextual awareness
- [x] Phase 5 — Integrated Learning: error_notebook, exercise→flashcard pipeline, mastery-aware study plans
- [x] Phase 6 — Multimodal: vision (screen/camera/OCR) + audio (VAD/wake word/STT/TTS/listener)
- [x] Phase 7 — Dashboard: mastery-by-subject bars, weekly summary, error summary, enhanced dashboard
- [x] Phase 8 — Gamification: XP system, 5 levels (Iniciante→Mestre), 26 achievements, leaderboard
- [x] Phase 9 — Security: rate limiting (slowapi), global exception handler
- [x] Phase 10 — Product: install.sh, doctor.sh, start/stop.sh, update.sh, backup.sh

### Infrastructure (V4)
- [x] Agent Loop V2: per-tool circuit breakers, retry with exponential backoff, MAX_STEPS=5
- [x] Observability: structured logging, request_id/session_id, health check (6 components)
- [x] Evidence Panel: frontend visualization of pipeline stages, badges, tools used
- [x] Exercise Engine V2: adaptive difficulty, review from error notebook, weak topics
- [x] Permission System V2: audit log, groups, hierarchy, temporary grants
- [x] Memory & Context V2: token estimation, context window trimming
- [x] Deployment: Dockerfile, docker-compose, nginx, .env.example
- [x] Caching: TTLCache LRU (OCR 128/2h, vision 64/30m, docs 32/24h)
- [x] RAG V2: embedding cache, reranking, metadata, page_range filter
- [x] Frontend Decomposition: Chat.tsx 993→357 lines, 3 hooks, 4 components
- [x] Performance: JPEG compression (~5x smaller), lazy loading panels
- [x] Tests: 537 backend + 18 frontend = 555 total
