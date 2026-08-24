# StudyAgent

Assistente multimodal de estudos que roda 100% local (Linux/Windows): chat com IA local via Ollama, visão computacional para ler a tela, OCR, memória de conversas em SQLite e sistema de permissões.

## Arquitetura V1

```
backend/app/
├── main.py              API FastAPI (chat, tela, permissões, cálculo)
├── config.py            Caminhos, modelos Ollama, variáveis de ambiente
├── agent/
│   ├── agent.py         Orquestrador + persona de tutor
│   ├── llm.py           Cliente Ollama (texto e visão)
│   └── memory.py        Memória de conversas (SQLite)
├── vision/
│   ├── screen.py        Captura de tela (mss), tela inteira ou região
│   └── ocr.py           OCR com Tesseract (opcional; a IA de visão também lê texto)
├── tools/calculator.py  Calculadora segura (parser AST)
└── security/permissions.py  Gerenciador de permissões
```

## Requisitos

- Python 3.12+
- Node 22+ (frontend, fase seguinte)
- Ollama com modelos `llama3.1` (texto) e `qwen2.5vl:7b` (visão)

## Instalação

```bash
cd ~/StudyAgent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Opcional — OCR nativo (a IA de visão já lê textos, mas o Tesseract é um fallback rápido):

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-por
```

Modelo de visão:

```bash
ollama pull qwen2.5vl:7b
```

Voz brasileira do Piper (não vem no repositório por tamanho):

```bash
mkdir -p backend/models/piper && cd backend/models/piper
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json
```

## Executando

Servidor da API:

```bash
cd ~/StudyAgent/backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Chat pelo terminal (sem navegador):

```bash
cd ~/StudyAgent/backend && source .venv/bin/activate
python ../scripts/cli_chat.py
```

No chat CLI:

- mensagem normal → conversa com o tutor
- `!tela me explica essa questão` → captura a tela e analisa
- `sair` → encerra

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Status, modelos disponíveis |
| POST | `/api/chat` | Conversa (`use_screen: true` anexa screenshot) |
| POST | `/api/screen/capture` | Captura a tela e retorna imagem + OCR |
| POST | `/api/screen/analyze` | Captura a tela e pede análise à IA |
| GET | `/api/permissions` | Lista permissões |
| PUT | `/api/permissions/{name}` | Ativa/desativa permissão |
| POST | `/api/calculate` | Calculadora segura |
| GET | `/api/sessions` | Lista sessões |

Exemplo:

```bash
curl -X POST localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "me explique equações de primeiro grau"}'

curl -X PUT localhost:8000/api/permissions/screen_capture \
  -H 'Content-Type: application/json' \
  -d '{"value": false}'
```

## Permissões

Controladas em `config/permissions.json`. Nenhum módulo acessa microfone, câmera, tela, arquivos ou internet sem checar antes. Padrão seguro: tudo desativado exceto `screen_capture` e `file_access`.

## Roadmap

- [x] Fase 1: chat, memória (com resumo rolante), captura de tela, permissões, OCR, voz (STT + TTS)
- [x] Fase 2a: câmera com reconhecimento, upload de PDF/txt com consulta no chat, telas ao vivo multi-monitor
- [ ] Fase 2b: gráficos dedicados, documentos avançados (docx)
- [ ] Fase 3: gerador de exercícios e quizzes dedicados na interface
- [ ] Fase 4: automação controlada (mouse/teclado com confirmação)
- [ ] Fase 5: memória entre sessões, perfil de aprendiz, plano de estudos

### Voz

- **Fala → texto:** faster-whisper `small` (CPU int8), ativado pelo botão 🎙 na interface
- **Texto → fala:** Piper com voz brasileira `pt_BR-faber-medium` (botão 🔊 liga/desliga a resposta falada)
- A permissão `microphone` precisa estar ativa para transcrever
