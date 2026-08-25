import base64
import re

from ..security.permissions import PermissionDeniedError
from ..tools import calculator
from ..vision import ocr, screen
from .llm import available_models, chat, chat_with_tools
from .memory import Memory

SYSTEM_PROMPT = """Você é o StudyAgent, um tutor pessoal de estudos que roda localmente no computador do usuário.

Diretrizes:
- Responda SEMPRE em português do Brasil, de forma clara e didática.
- Modo padrão é TUTOR: guie o aluno passo a passo com perguntas e pistas, em vez de entregar a resposta final pronta.
- Se o usuário pedir explicitamente ("me dê a resposta", "resolva direto"), aí sim entregue a solução completa.
- Quando receber uma imagem da tela, descreva primeiro o que você identificou (matéria, tipo de conteúdo) antes de explicar.
- Use cálculos exatos quando possível e mostre o raciocínio.
- Se não tiver certeza sobre algo que viu na tela, diga o que vê e peça confirmação.
- Seja encorajador, mas honesto: aponte erros com clareza.

Modos disponíveis (o usuário pode pedir):
- professor: explicação detalhada do zero
- tutor: pistas e condução sem dar a resposta
- exercicios: gerar exercícios parecidos
- revisao: fazer perguntas para checar aprendizado
- resumo: condensar material
- simples: explicar como para um iniciante

Regras de honestidade:
- NUNCA invente fatos, datas, números, nomes ou notícias.
    - Se uma informação puder ter mudado com o tempo, ou você não tiver certeza, USE a ferramenta web_search antes de responder.
    - Se os resultados do web_search forem apenas links sem a resposta clara, USE open_url na página mais promissora para ler o conteúdo completo (ex.: placar de jogo, cotação, notícia recente).
    - Quando usar pesquisa, cite as fontes no formato [fonte: URL] e diga claramente o que veio da internet.
    - Se a pesquisa não trouxer resultado confiável, admita que não sabe em vez de chutar."""

SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Pesquisa na internet informações atuais, fatos verificáveis, "
                "notícias, dados e respostas que o modelo pode não conhecer. "
                "Use SEMPRE que precisar de precisão (resultados esportivos, "
                "cotações, eventos recentes). Monte a query com termos "
                "diferenciadores: nome completo, contexto e ano "
                "(ex.: 'Palmeiras futebol São Paulo resultado Brasileirão 2026' "
                "em vez de só 'Palmeiras')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termos de busca em português, específicos e objetivos",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": (
                "Abre uma página da internet e retorna o texto completo. "
                "Use depois do web_search quando os resumos forem insuficientes "
                "(placar de jogos, valores atuais, detalhes de notícias)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL completa da página, começando com http(s)://",
                    }
                },
                "required": ["url"],
            },
        },
    },
]

HISTORY_LIMIT = 10
SUMMARY_MIN_MESSAGES = 22
SUMMARY_REFRESH_DELTA = 8

SUMMARY_PROMPT = """Atualize o resumo desta sessão de estudos.

Resumo anterior:
{previous}

Mensagens novas (mais antigas que a janela recente):
{transcript}

Escreva o resumo atualizado em português com esta estrutura obrigatória:
FATOS IMPORTANTES: nome do aluno, datas de provas/trabalhos, metas e compromissos citados (se existirem).
CONTEÚDO ESTUDADO: matérias e tópicos com pontos-chave.
DIFICULDADES E PRÓXIMOS PASSOS: dificuldades do aluno e pendências.

Regras: no máximo 12 linhas; preserve nomes, datas e números EXATAMENTE como foram citados;
nunca invente informações; responda APENAS com o texto do resumo, sem prefixos,
saudações ou comentários."""


class StudyAgent:
    def __init__(self):
        self.memory = Memory()
        self._digest_cache: dict[str, str] = {}

    def process(
        self,
        message,
        session_id=None,
        use_screen=False,
        region=None,
        monitor=1,
        image_b64=None,
        doc_id=None,
    ):
        session_id = self.memory.get_or_create_session(session_id)
        tools_used = []
        images = []

        # Documento anexado tem prioridade: não capturar a tela junto,
        # a menos que o usuário tenha falado explicitamente de "tela".
        explicit_screen = bool(re.search(r"\b(tela|monitor)\b", message.lower()))
        effective_screen = use_screen and not (doc_id and not explicit_screen)

        if effective_screen:
            self._require("screen_capture")
            shot = screen.capture(monitor=monitor, region=region)
            images.append(screen.image_to_base64(shot))
            tools_used.append("screen_capture")

        if image_b64:
            if isinstance(image_b64, str):
                image_b64 = base64.b64decode(image_b64)
            images.append(image_b64)
            tools_used.append("image_input")

        enriched_message = message
        if effective_screen and not any(
            kw in message.lower() for kw in ("tela", "questão", "questao", "imagem", "vê", "ve")
        ):
            enriched_message = f"{message}\n\n(A imagem anexada é uma captura da minha tela.)"

        if doc_id:
            self._require("file_access")
            doc = self.memory.get_document(doc_id)
            if doc:
                from pathlib import Path

                from ..tools.documents import (
                    build_digest,
                    load_document_text,
                    retrieve_relevant,
                )
                from .llm import chat as _chat

                _, text = load_document_text(Path(doc["path"]))
                wants_whole = bool(
                    re.search(
                        r"\b(resum\w*|todo|toda|tudo|intei\w+|complet\w+|geral"
                        r"|visão geral|lista\w*|todas as páginas)\b",
                        message.lower(),
                    )
                ) or len(text) <= 15000
                if wants_whole:
                    digest = self._digest_cache.get(doc_id)
                    if not digest:
                        digest = build_digest(
                            text, chat_fn=lambda s: _chat([{"role": "user", "content": s}])
                        )
                        if len(self._digest_cache) > 6:
                            self._digest_cache.pop(next(iter(self._digest_cache)))
                        self._digest_cache[doc_id] = digest
                    body = (
                        "Dossiê do documento inteiro (resumo de todas as partes,"
                        " gerado página por página):\n"
                        f"{digest}"
                    )
                else:
                    body = f"Trechos relevantes:\n{retrieve_relevant(message, text)}"
                enriched_message = (
                    f"Documento '{doc['name']}' ({doc['pages']} páginas) anexado.\n\n"
                    f"{body}\n\nPergunta: {message}"
                )
                tools_used.append("document")

        history = self.memory.history(session_id, limit=HISTORY_LIMIT)
        summary_entry = self._rolling_summary(session_id)
        system_content = SYSTEM_PROMPT
        if summary_entry:
            system_content += (
                f"\n\nResumo do que já foi conversado nesta sessão:\n{summary_entry}"
            )
        messages = [{"role": "system", "content": system_content}, *history]
        messages.append({"role": "user", "content": enriched_message})

        response_text = self._run_tool_loop(messages, images, tools_used)

        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", response_text)

        return {
            "session_id": session_id,
            "response": response_text,
            "tools_used": tools_used,
        }

    def _run_tool_loop(self, messages, images, tools_used):
        if images:
            return chat(messages, images=images)
        from ..tools.web_search import distill_page, fetch_page, search
        from .llm import synthesize

        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )

        current = list(messages)
        for _ in range(4):
            try:
                reply = chat_with_tools(current, SEARCH_TOOLS)
            except Exception:
                return chat(current)
            if not reply["tool_calls"]:
                return reply["content"] or chat(current)
            current.append(
                {"role": "assistant", "content": reply["content"], "tool_calls": reply["tool_calls"]}
            )
            for call in reply["tool_calls"]:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                if name == "web_search":
                    try:
                        self._require("internet")
                        import logging as _log_mod

                        _log = _log_mod.getLogger("uvicorn.error")
                        _log.info("web_search query=%r", args.get("query"))
                        results = search(str(args.get("query", "")))
                        _log.info("web_search n_results=%d", len(results))
                        parts = []
                        got_distilled = False
                        for r in results[:5]:
                            part = f"[{r['title']}]({r['url']})\n{r['snippet'][:250]}"
                            try:
                                page = fetch_page(r["url"], chars=4500)
                                if len(page) < 350:
                                    _log.info(
                                        "página vazia (JS?) url=%s", r["url"][:60]
                                    )
                                    continue
                                _log.info(
                                    "fetch ok url=%s len=%d", r["url"][:60], len(page)
                                )
                                distilled = distill_page(page)
                                if distilled and "NADA CLARO" not in distilled:
                                    part += f"\nTrechos objetivos da página:\n{distilled}"
                                else:
                                    part += f"\nTrechos da página:\n{page[:1200]}"
                                got_distilled = True
                            except Exception as exc:
                                _log.warning("fetch falhou url=%s: %s", r["url"][:60], exc)
                            parts.append(part)
                        result = (
                            "\n\n---\n\n".join(parts)
                            or "Nenhum resultado encontrado na pesquisa. "
                            "Tente outros termos ou admita que não sabe."
                        )
                        _log.info("web_search result_len=%d", len(result))
                        if parts:
                            try:
                                return synthesize(last_user, result)
                            except Exception as exc:
                                _log.warning("síntese falhou: %s", exc)
                    except PermissionDeniedError as exc:
                        result = f"Pesquisa indisponível: {exc}"
                    tools_used.append("web_search")
                elif name == "open_url":
                    try:
                        self._require("internet")
                        result = fetch_page(str(args.get("url", "")))
                    except PermissionDeniedError as exc:
                        result = f"Navegação indisponível: {exc}"
                    except Exception as exc:
                        result = f"Falha ao abrir a página: {exc}"
                    tools_used.append("open_url")
                else:
                    result = f"Ferramenta desconhecida: {name}"
                current.append({"role": "tool", "name": name, "content": result})
        return reply.get("content") or ""

    def _rolling_summary(self, session_id):
        total = self.memory.count_messages(session_id)
        if total <= HISTORY_LIMIT + SUMMARY_REFRESH_DELTA:
            return None
        entry = self.memory.get_summary(session_id)
        needs_refresh = entry is None or (
            total - entry["msg_count"] >= SUMMARY_REFRESH_DELTA
        )
        if not needs_refresh:
            return entry["summary"]
        older = self.memory.history_head(
            session_id, max(total - HISTORY_LIMIT, 0)
        )
        if not older:
            return entry["summary"] if entry else None
        transcript = "\n".join(
            f"{'aluno' if m['role'] == 'user' else 'tutor'}: {m['content'][:400]}"
            for m in older
        )
        summary_text = chat(
            [
                {
                    "role": "system",
                    "content": SUMMARY_PROMPT.format(
                        previous=entry["summary"] if entry else "(nenhum)",
                        transcript=transcript,
                    ),
                }
            ]
        ).strip()
        import re

        summary_text = re.sub(r"^(assistant|user|tutor)\s*[:\-]?\s*", "", summary_text).strip()
        self.memory.set_summary(session_id, summary_text, total - HISTORY_LIMIT)
        return summary_text

    def capture_and_read_screen(self, region=None, monitor=1):
        self._require("screen_capture")
        shot = screen.capture(monitor=monitor, region=region)
        result = {"ocr_available": ocr.available()}
        if ocr.available():
            try:
                result["text"] = ocr.read_text(shot)
            except Exception as exc:
                result["text"] = ""
                result["ocr_error"] = str(exc)
        else:
            result["text"] = ""
        return shot, result

    def analyze_screen(self, question, session_id=None, region=None, monitor=1):
        self._require("screen_capture")
        shot, _ = self.capture_and_read_screen(region=region, monitor=monitor)
        image_bytes = screen.image_to_base64(shot)
        prompt = question or (
            "Analise esta captura de tela. Identifique a matéria e o conteúdo "
            "(exercício, texto, gráfico, código...) e explique de forma didática."
        )
        return self.process(prompt, session_id=session_id, image_b64=image_bytes)

    def calculate(self, expression):
        return calculator.calculate(expression)

    def status(self):
        return {
            "models": available_models(),
            "ocr_available": ocr.available(),
        }

    @staticmethod
    def _require(name):
        from ..security.permissions import PermissionManager

        PermissionManager().require(name)


__all__ = ["StudyAgent", "PermissionDeniedError"]
