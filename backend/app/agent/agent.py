import base64
import logging

from ..core.context_manager import (
    ContextManager,
    build_document_block,
    digest_body,
    excerpts_body,
    whole_doc_body,
)
from ..core.model_manager import available_models
from ..core.planner import WHOLE_DOC_MAX_CHARS, build_plan
from ..core.registered_tools import calculate_tool, open_url_tool, web_search_tool  # noqa: F401
from ..core.tool_registry import all_schemas, get
from ..core.vision_router import build_image_note, decide_ocr_block, format_window_note
from ..security.permissions import PermissionDeniedError
from ..tools import calculator
from ..vision import ocr, screen, window
from .llm import chat, chat_with_tools
from .memory import Memory


class StudyAgent:
    def __init__(self):
        self.memory = Memory()
        self.ctx = ContextManager(
            self.memory,
            summarize_fn=lambda prompt: chat([{"role": "system", "content": prompt}]),
        )
        self._digest_cache: dict[str, str] = {}
        self._session_docs: dict[str, str] = {}

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

        # ── Planner V2: decisões centralizadas ──────────────────────────
        plan = build_plan(
            message,
            use_screen_requested=bool(use_screen),
            camera_image=image_b64 is not None,
            requested_doc_id=doc_id,
            session_doc_id=self._session_docs.get(session_id),
        )
        if plan.monitor:
            monitor = plan.monitor

        ocr_text = None
        if plan.capture_screen:
            self._require("screen_capture")
            shot = screen.capture(monitor=monitor, region=region)
            images.append(screen.image_to_base64(shot))
            tools_used.append("screen_capture")
            ocr_text = self._safe_ocr(shot)

        camera_image = image_b64 is not None
        if image_b64:
            if isinstance(image_b64, str):
                image_b64 = base64.b64decode(image_b64)
            images.append(image_b64)
            tools_used.append("image_input")
            ocr_text = ocr_text or self._safe_ocr_bytes(image_b64)

        msg_parts = [message]
        if images:
            size = shot.size if plan.capture_screen else None
            msg_parts.append(
                build_image_note(
                    camera=camera_image,
                    monitor=None if camera_image else monitor,
                    size=size,
                )
            )
            if not camera_image:
                janela = format_window_note(window.active_window())
                if janela:
                    msg_parts.append(janela)
            bloco_ocr = decide_ocr_block(ocr_text)
            if bloco_ocr:
                msg_parts.append(bloco_ocr)

        # ── Documento anexado / lembrado pela sessão ─────────────────────
        if plan.wants_document:
            self._require("file_access")
            doc = self.memory.get_document(plan.doc_id)
            if doc:
                from pathlib import Path

                from ..tools.documents import (
                    build_digest,
                    load_document_text,
                    retrieve_relevant,
                )

                _, text = load_document_text(Path(doc["path"]))
                if len(text) <= WHOLE_DOC_MAX_CHARS:
                    # Cabe inteiro no contexto: manda o documento completo,
                    # sem resumo que possa perder detalhes.
                    body = whole_doc_body(text)
                elif plan.whole_doc:
                    digest = self._digest_cache.get(plan.doc_id)
                    if not digest:
                        digest = build_digest(
                            text, chat_fn=lambda s: chat([{"role": "user", "content": s}])
                        )
                        if len(self._digest_cache) > 6:
                            self._digest_cache.pop(next(iter(self._digest_cache)))
                        self._digest_cache[plan.doc_id] = digest
                    body = digest_body(digest)
                else:
                    body = excerpts_body(retrieve_relevant(message, text))
                msg_parts.append(
                    build_document_block(doc["name"], doc["pages"], body)
                )
                tools_used.append("document")
                self._session_docs[session_id] = plan.doc_id
                if len(self._session_docs) > 50:
                    self._session_docs.pop(next(iter(self._session_docs)))

        enriched_message = "\n\n".join(msg_parts)

        messages = self.ctx.assemble(session_id, enriched_message)

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
        from .llm import synthesize

        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )

        current = list(messages)
        for _ in range(4):
            try:
                reply = chat_with_tools(current, all_schemas())
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
                entry = get(name)
                if not entry:
                    result = f"Ferramenta desconhecida: {name}"
                else:
                    try:
                        if entry.permission:
                            self._require(entry.permission)
                        logging.getLogger("uvicorn.error").info(
                            "tool=%s args=%s", name, str(args)[:120]
                        )
                        result = entry.handler(args)
                    except PermissionDeniedError as exc:
                        result = f"Permissão negada para {name}: {exc}"
                    except Exception as exc:
                        result = f"Falha ao executar {name}: {exc}"
                    tools_used.append(name)
                    # Busca bem-sucedida → síntese dedicada com citações
                    if name == "web_search" and "---" in result:
                        try:
                            return synthesize(last_user, result)
                        except Exception as exc:
                            logging.getLogger("uvicorn.error").warning(
                                "síntese falhou: %s", exc
                            )
                current.append({"role": "tool", "name": name, "content": result})
        return reply.get("content") or ""

    @staticmethod
    def _safe_ocr(pil_image):
        if not ocr.available():
            return None
        try:
            return ocr.read_text(pil_image)
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning("OCR falhou: %s", exc)
            return None

    @staticmethod
    def _safe_ocr_bytes(data):
        from io import BytesIO

        from PIL import Image

        try:
            return StudyAgent._safe_ocr(Image.open(BytesIO(data)))
        except Exception:
            return None

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
