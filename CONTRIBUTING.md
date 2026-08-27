# Contribuindo com o StudyAgent

Obrigado por contribuir! Este guia explica como participar do desenvolvimento.

## Pré-requisitos

- Python 3.12+
- Node.js 18+
- Ollama instalado com modelos: `llama3.1`, `qwen2.5vl:7b`, `nomic-embed-text`
- Tesseract OCR: `sudo apt install tesseract-ocr tesseract-ocr-por`

## Configuração do Ambiente

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd frontend
npm install
```

## Estrutura do Projeto

```
StudyAgent/
├── backend/
│   ├── app/
│   │   ├── agent/          # Orquestração, loop de ferramentas
│   │   ├── core/           # Cache, health, planner, context, registry
│   │   ├── orchestrator/   # Execution plan, evidence, validator
│   │   ├── vision/         # Captura, OCR, processamento
│   │   ├── audio/          # STT, TTS, VAD, wake word
│   │   ├── tools/          # Calculadora, RAG, web search
│   │   ├── tutor/          # Flashcards, planos, perfil, gamificação
│   │   ├── security/       # Permissões
│   │   └── routers/        # Endpoints HTTP
│   └── tests/              # Testes pytest
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── hooks/          # Custom hooks (useChat, useVoice, useScreen)
│   │   └── test/           # Testes Vitest
│   └── ...
└── docs/
    ├── ARCHITECTURE_AUDIT.md
    └── API.md
```

## Regras de Implementação

1. **NUNCA** começar do zero — sempre auditar → corrigir → melhorar → testar → commitar
2. **NÃO** remover funcionalidades existentes sem justificativa
3. **NÃO** quebrar APIs existentes (versionar se necessário)
4. **NÃO** criar mocks para mascarar bugs reais
5. **NÃO** declarar conclusão sem teste
6. **PRIMEIRO** rodar testes antes e depois de cada alteração

## Fluxo de Trabalho

### 1. Criar branch
```bash
git checkout -b feature/nome-da-feature
```

### 2. Fazer alterações
- Seguir o estilo de código existente
- Adicionar testes para nova funcionalidade
- Manter 100% local/offline

### 3. Rodar testes
```bash
# Backend
cd backend
.venv/bin/pytest tests/ -v
.venv/bin/ruff check app/ tests/

# Frontend
cd frontend
npx tsc --noEmit
npx vitest run
npx vite build
```

### 4. Commitar
```bash
git add .
git commit -m "tipo: descrição breve"

# Tipos: feat, fix, test, docs, refactor, perf
```

### 5. Push e PR
```bash
git push origin feature/nome-da-feature
```

## Convenções de Código

### Python
- Seguir PEP 8 (ruff como linter)
- Type hints em todas as funções públicas
- Docstrings em português
- Nomes: snake_case para funções/variáveis, PascalCase para classes

### TypeScript/React
- TypeScript strict mode
- Componentes em arquivos separados
- Hooks customizados em `src/hooks/`
- Estilos em `index.css` (CSS puro)

### Commits
- Formato: `tipo(escopo): descrição`
- Exemplos:
  - `feat(vision): add image compression`
  - `fix(cache): handle concurrent access`
  - `test(edge): add cache thread safety tests`
  - `docs: update API reference`

## Testes

### Backend (pytest)
```bash
cd backend
.venv/bin/pytest tests/ -v --tb=short
```

### Frontend (Vitest)
```bash
cd frontend
npx vitest run
```

### Cobertura mínima
- Novas funcionalidades: mínimo 1 teste
- Bugs corrigidos: teste de regressão
- Edge cases: testar limites e erros

## Areas de Contribuição

### Prioridade Alta
- Testes de integração end-to-end
- Testes frontend (componentes críticos)
- Performance de OCR e embeddings

### Prioridade Média
- Documentação de API
- Melhorias de UX
- Novos exercícios e flashcards

### Prioridade Baixa
- Refatoração de código existente
- Otimizações de bundle
- Acessibilidade

## Problemas Conhecidos

- PortAudio não instalado (usa ALSA subprocess)
- 1 teste pre-existente falhando: `test_ferramentas_padrao_registradas`
- Testes full E2E requerem Ollama rodando

## Perguntas?

Abra uma issue no GitHub: https://github.com/ANTONIOALGMAR/StudyAgent/issues
