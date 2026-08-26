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
from ..core.vision_router import (
    VisionContext,
    VisionIntent,
    build_image_note,
    decide_ocr_block,
    format_window_note,
)
from ..security.permissions import PermissionDeniedError
from ..vision import ocr, screen, window
from ..vision.engine import process_capture
from ..vision.screen import ScreenManager
from .llm import chat, chat_with_tools
from .memory import Memory

log = logging.getLogger("studyagent.vision")


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
        vision_ctx = None

        if plan.capture_screen:
            vision_ctx = self._vision_pipeline(
                message=message,
                monitor=monitor,
                region=region,
                intent=plan.vision_intent,
            )
            if not vision_ctx.is_valid:
                log.error("[VISION] pipeline_failed errors=%s", vision_ctx.errors)
                return {
                    "session_id": session_id,
                    "response": (
                        "Não consegui capturar ou analisar a tela. "
                        + "; ".join(vision_ctx.errors)
                    ),
                    "tools_used": [],
                }
            tools_used.append("screen_capture")
            images.append(vision_ctx.image_bytes)
            ocr_text = vision_ctx.ocr_text

        camera_image = image_b64 is not None
        if image_b64:
            if isinstance(image_b64, str):
                image_b64 = base64.b64decode(image_b64)
            images.append(image_b64)
            tools_used.append("image_input")
            ocr_text = ocr_text or self._safe_ocr_bytes(image_b64)
            log.info("[VISION] camera_image=attached bytes=%d", len(image_b64))

        msg_parts = [message]
        if images and not vision_ctx:
            msg_parts.append(
                build_image_note(
                    camera=camera_image,
                    monitor=None if camera_image else monitor,
                    size=None,
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
                    trechos = None
                    try:
                        from ..tools import rag

                        trechos = rag.search(plan.doc_id, text, message)
                    except Exception as exc:
                        logging.getLogger("uvicorn.error").warning(
                            "RAG falhou: %s", exc
                        )
                    if not trechos:
                        trechos = retrieve_relevant(message, text)
                    body = excerpts_body(trechos)
                msg_parts.append(
                    build_document_block(doc["name"], doc["pages"], body)
                )
                tools_used.append("document")
                self._session_docs[session_id] = plan.doc_id
                if len(self._session_docs) > 50:
                    self._session_docs.pop(next(iter(self._session_docs)))

        enriched_message = "\n\n".join(msg_parts)

        # Pipeline de visão: system prompt DIRECIONADO para análise visual
        if vision_ctx and vision_ctx.is_valid:
            messages = self.ctx.assemble_vision(session_id, enriched_message, vision_ctx)
        else:
            messages = self.ctx.assemble(session_id, enriched_message)

        # Com documento anexado não há necessidade de ferramentas
        response_text = self._run_tool_loop(
            messages, images, tools_used, allow_tools=not plan.wants_document
        )

        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", response_text)

        return {
            "session_id": session_id,
            "response": response_text,
            "tools_used": tools_used,
        }

    def _run_tool_loop(self, messages, images, tools_used, allow_tools=True):
        if images:
            log.info("[VISION] vision_model=sending images=%d message_count=%d",
                     len(images), len(messages))
            response = chat(messages, images=images)
            log.info("[VISION] vision_response=length=%d",
                     len(response) if response else 0)
            return response
        if not allow_tools:
            return chat(messages)
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
                    if name == "web_search" and "---" in result:
                        try:
                            return synthesize(last_user, result)
                        except Exception as exc:
                            logging.getLogger("uvicorn.error").warning(
                                "síntese falhou: %s", exc
                            )
                current.append({"role": "tool", "name": name, "content": result})
        return reply.get("content") or ""

    def _vision_pipeline(
        self,
        message: str,
        monitor: int,
        region,
        intent: VisionIntent,
    ) -> VisionContext:
        """Pipeline dedicado de visão: captura → processa → contexto.

        Fluxo explícito com estados registrados.
        """
        stages = []
        errors = []

        # ── Stage 1: CAPTURE ────────────────────────────────────────
        self._require("screen_capture")
        log.info("[VISION] stage=CAPTURE_REQUESTED monitor=%s", monitor)
        stages.append("CAPTURE_REQUESTED")

        try:
            shot = ScreenManager.capture_monitor(monitor_id=monitor, region=region)
        except Exception as exc:
            errors.append(f"Falha na captura: {exc}")
            log.error("[VISION] stage=CAPTURE_FAILED error=%s", exc)
            return VisionContext(source="screen", monitor_id=monitor, errors=errors)

        capture_res = screen.validate_capture(shot, monitor)
        if not capture_res.is_valid:
            errors.append(capture_res.error or "Captura inválida")
            log.error("[VISION] stage=CAPTURE_INVALID error=%s", capture_res.error)
            return VisionContext(source="screen", monitor_id=monitor, errors=errors)

        stages.append("CAPTURED")
        log.info("[VISION] stage=CAPTURED resolution=%dx%d monitor=%s",
                 capture_res.width, capture_res.height, monitor)

        # ── Stage 2: WINDOW INFO ────────────────────────────────────
        window_info = None
        try:
            window_info = window.active_window()
        except Exception:
            pass

        # ── Stage 3: PROCESS (OCR + context) ────────────────────────
        # process_capture é puro — sem LLM. Só OCR + janela.
        ctx = process_capture(shot, monitor, window_info)
        ctx.errors = errors
        return ctx

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
        shot = ScreenManager.capture_monitor(monitor_id=monitor, region=region)
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
