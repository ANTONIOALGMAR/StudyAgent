# StudyAgent

Tutor de estudos multimodal que roda **100% local** no seu computador (Linux): chat com IA local via Ollama, voz nos dois sentidos, visão computacional para ler telas e câmera, leitura completa de PDFs, pesquisa na internet com fontes citadas, gerador de exercícios com correção automática — tudo sob um sistema de permissões explícitas.

## Funcionalidades

### 💬 Conversa com tutor de IA
- Modelos locais via Ollama (`llama3.1` texto, `qwen2.5vl:7b` visão) — nada sai do computador
- Persona de tutor configurável: professor, tutor (dá pistas sem entregar a resposta), exercícios, revisão, resumo, simples
- Memória rolante: últimas mensagens + resumo automático da sessão (fatos importantes, conteúdo estudado, dificuldades)
- Calculadora segura embutida

### 🗣 Voz completa
- **Fala → texto:** faster-whisper `small`, botão 🎙 aperta-para-falar
- **Modo conversa automática 🔄:** o agente ouve continuamente (VAD no navegador), transcreve, responde e fala — mão livre
- **Texto → fala:** Piper com voz brasileira `pt_BR-faber-medium`

### 👀 Visão
- 🖥 Anexo captura de tela à mensagem
- 📺 Painel *ao vivo* multi-monitor com atualização contínua e **modo comentarista** (o agente avisa quando algo muda na tela); painel minimizável
- 📷 Câmera: aponte, capture e pergunte

### 📄 Documentos
- Upload de PDF/txt/md com extração de texto
- **Leitura integral (map-reduce):** pediu resumo ou "o documento todo"? O PDF é dividido em partes, cada uma é resumida e vira um dossiê completo — nada fica de fora, mesmo em arquivos grandes (com cache por documento)
- **Leitor integrado:** visualize o PDF dentro do app enquanto conversa sobre ele
- Documento anexado tem prioridade sobre captura de tela

### 🌐 Pesquisa na internet (com honestidade)
- Cascata de buscadores: DuckDuckGo → Bing → Wikipédia
- Abre automaticamente as páginas mais relevantes, extrai e destila os fatos objetivos
- Síntese final com o modelo de visão + regras de desambiguação (não confunde entidades homônimas)
- Sempre cita fontes `[fonte: URL]`; se não achar, admite que não sabe em vez de inventar

### 🎯 Exercícios
- Gera questões do tema que você escolher (múltipla escolha ou dissertativas)
- Gabarito fica no servidor — correção automática aceitando respostas equivalentes (`0,5` = `1/2`)
- Barra de pontuação, gabarito comentado nas erradas

### 🎭 Interface
- Rosto animado do agente que reage: pensa, ouve, grava, fala — e **reage ao conteúdo** (fica feliz quando te elogia, preocupado quando te corrige, curioso quando pergunta)
- **Modo palco:** rosto em tela cheia (⤢, Esc para sair)
- Sidebar de ferramentas sanfona (recolhe pra ícones) + painel de permissões recolhível
- Tema escuro, tudo em português

## Arquitetura

```
backend/app/
├── main.py              API FastAPI (chat, tela, áudio, docs, exercícios, permissões)
├── config.py            Caminhos, modelos Ollama
├── core/                Núcleo V2 (desacoplado do agente)
│   ├── model_manager.py    Papéis de modelos por env (text/vision/synthesis/stt/tts)
│   ├── planner.py          Decide captura de tela, monitor e estratégia de documento
│   ├── context_manager.py  System prompt, resumo rolante, montagem de contexto
│   ├── vision_router.py    Notas de imagem, bloco híbrido de OCR, janela ativa
│   ├── tool_registry.py    Registro decorado de ferramentas + schemas p/ tool-calling
│   └── registered_tools.py web_search, open_url, calculate
├── agent/
│   ├── agent.py         Orquestrador: plano → ferramentas → resposta
│   ├── llm.py           Cliente Ollama + síntese de pesquisas (qwen2.5vl)
│   ├── memory.py        SQLite: sessões, mensagens, resumos, documentos
│   └── exercises.py     Gerador de questões + corretor com equivalência
├── vision/
│   ├── screen.py        Captura multi-monitor (mss + cosmic-screenshot p/ Wayland)
│   ├── window.py        Janela ativa (xdotool/swaymsg; None em Wayland sem suporte)
│   └── ocr.py           OCR Tesseract (híbrido com a visão do modelo)
├── audio/
│   ├── speech_to_text.py  faster-whisper
│   └── text_to_speech.py  Piper
├── tools/
│   ├── calculator.py    Avaliador AST seguro
│   ├── documents.py     Extração PDF, digest map-reduce, RAG semântico, narração
│   ├── rag.py           Busca semântica local (nomic-embed-text + numpy)
│   └── web_search.py    DDG→Bing→Wikipédia, fetch de páginas, destilação
└── security/permissions.py  Portão de permissões

frontend/src/
├── App.tsx              Layout: painel de permissões sanfona + chat
├── components/
│   ├── Chat.tsx         Núcleo da UI (conversa, voz, telas, câmera)
│   ├── AgentFace.tsx    Rosto SVG expressivo
│   ├── Sidebar.tsx      Ferramentas sanfona
│   ├── ExercisesPanel.tsx  Quiz com correção
│   ├── PdfViewer.tsx    Leitor de documentos
│   └── PermissionsPanel.tsx
└── api.ts               Cliente tipado da API
```

### Testes

O backend tem suíte pytest (planner, registry, calculadora, documentos,
exercícios, permissões) e lint ruff:

```bash
cd backend
.venv/bin/python -m pytest -q      # testes
.venv/bin/python -m ruff check app tests
```

CI roda em cada push via GitHub Actions (`.github/workflows/backend.yml`).

Modelos são configuráveis por variável de ambiente (`STUDY_TEXT_MODEL`,
`STUDY_VISION_MODEL`, `STUDY_SYNTH_MODEL`, `STUDY_EMBEDDING_MODEL`,
`STUDY_STT_MODEL`, `STUDY_TTS_MODEL`) — sem nomes fixos no código.

## Requisitos

- Linux (Pop!_OS testado, inclui Wayland/COSMIC)
- Python 3.12+, Node 22+
- Ollama com `llama3.1` e `qwen2.5vl:7b`
- GPU recomendada (RTX 3060 12GB roda tudo)

## Instalação

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
```

Voz brasileira do Piper (não vai no repo por tamanho):

```bash
mkdir -p backend/models/piper && cd backend/models/piper
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json
```

OCR nativo (opcional):

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-por
```

## Executando

Com os serviços systemd (sobem no boot, reiniciam sozinhos):

```bash
cp scripts/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now studyagent-ollama studyagent-api studyagent-web
```

Ou manualmente:

```bash
# terminal 1
ollama serve
# terminal 2
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
# terminal 3
cd frontend && npx vite --port 5173
```

Abra **http://localhost:5173**

CLI de controle: `studyagent start|stop|status|restart|logs`

Chat pelo terminal:

```bash
cd backend && source .venv/bin/activate && python ../scripts/cli_chat.py
```

- mensagem normal → conversa com o tutor
- `!tela me explica essa questão` → captura a tela e analisa
- `sair` → encerra

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Status e modelos |
| POST | `/api/chat` | Conversa (`use_screen`, `image_b64`, `doc_id`) |
| POST | `/api/screen/capture` | Captura + OCR |
| GET | `/api/screen/monitors` | Lista monitores |
| GET | `/api/screen/preview` | JPEG do monitor (painel ao vivo) |
| POST | `/api/screen/analyze` | Análise de tela pela IA |
| POST | `/api/audio/transcribe` | Áudio → texto (Whisper) |
| POST | `/api/audio/speak` | Texto → áudio WAV (Piper) |
| POST | `/api/calculate` | Calculadora segura |
| POST | `/api/documents/upload` | Upload pdf/txt/md |
| GET | `/api/documents/{id}/file` | Arquivo original (leitor) |
| GET | `/api/documents/{id}/audio/plan` | Plano do audiobook (total de partes) |
| GET | `/api/documents/{id}/audio?idx=N` | Áudio WAV da parte N (🎧 acessibilidade) |
| POST | `/api/exercises/generate` | Gera questões (gabarito fica no servidor) |
| POST | `/api/exercises/grade` | Corrige com equivalência de respostas |
| GET | `/api/sessions` | Lista sessões |
| GET/PUT | `/api/permissions[/{name}]` | Permissões |

## Permissões

Controladas pelo painel lateral (ou `config/permissions.json`). Nenhum módulo acessa microfone, câmera, tela, arquivos ou internet sem checar antes.

## Roadmap

- [x] Fase 1: chat, memória rolante, captura de tela, permissões, OCR, voz (STT + TTS), calculadora
- [x] Fase 2a: câmera, upload de documentos com consulta, telas ao vivo multi-monitor
- [x] Fase 3: gerador de exercícios e quizzes com correção automática
- [x] Extras: rosto expressivo com emoções, modo palco, leitura integral de PDFs, leitor integrado, pesquisa web com fontes, serviços systemd
- [ ] Fase 2b: gráficos dedicados, documentos avançados (docx)
- [ ] Fase 4: automação controlada (mouse/teclado com confirmação)
- [ ] Fase 5: memória entre sessões, perfil de aprendiz, plano de estudos, dashboard
