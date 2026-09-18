"""Router: Chat e sessões.

Endpoints:
- POST /api/chat         → resposta completa (JSON, compatibilidade)
- POST /api/chat/stream  → resposta em streaming token-a-token (SSE)
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..agent.agent import PermissionDeniedError, StudyAgent
from ..core.structured_logging import set_session_id

router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)
log = logging.getLogger("studyagent.router.chat")

agent = StudyAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    use_screen: bool = False
    region: dict | None = None
    monitor: int | None = None
    camera_image: str | None = None
    doc_id: str | None = None


@router.get("/health")
def health():
    return {"status": "ok", **agent.status()}


@router.post("/chat")
@limiter.limit("15/minute")
def chat(request: Request, req: ChatRequest):
    try:
        from ..security.permissions import PermissionManager
        if req.camera_image:
            PermissionManager().require("camera")
        if req.use_screen:
            PermissionManager().require("screen_capture")
        result = agent.process(
            req.message,
            session_id=req.session_id,
            use_screen=req.use_screen,
            region=req.region,
            monitor=req.monitor,
            camera_image=req.camera_image,
            doc_id=req.doc_id,
        )
        if result.get("session_id"):
            set_session_id(result["session_id"])
        log.info(
            "[CHAT] msg_len=%d tools=%s evidence=%s",
            len(req.message),
            result.get("tools_used", []),
            "yes" if result.get("evidence") else "no",
        )
        return result
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _sse(event: dict) -> str:
    """Serializa um evento do pipeline no formato SSE."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
@limiter.limit("15/minute")
def chat_stream_endpoint(request: Request, req: ChatRequest):
    """Streaming SSE (text/event-stream) da resposta do agente.

    Eventos (payload JSON em `data:`):
    - {"type": "start", "session_id": ...}
    - {"type": "token", "text": ...}      (fragmentos; concatenar para a resposta)
    - {"type": "done", "result": {...}}   (mesmo shape de POST /api/chat)
    - {"type": "error", "detail": ...}    (falha em runtime)
    - "data: [DONE]"                       (sentinela de fim de stream)
    """
    try:
        from ..security.permissions import PermissionManager
        if req.camera_image:
            PermissionManager().require("camera")
        if req.use_screen:
            PermissionManager().require("screen_capture")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    def _generate():
        try:
            for event in agent.process_events(
                req.message,
                session_id=req.session_id,
                use_screen=req.use_screen,
                region=req.region,
                monitor=req.monitor,
                camera_image=req.camera_image,
                doc_id=req.doc_id,
            ):
                if event["type"] == "done" and event["result"].get("session_id"):
                    set_session_id(event["result"]["session_id"])
                yield _sse(event)
        except PermissionDeniedError as exc:
            yield _sse({"type": "error", "detail": str(exc)})
        except Exception as exc:
            log.exception("[CHAT_STREAM] stream_failed: %s", exc)
            yield _sse(
                {"type": "error", "detail": "Erro interno do servidor"}
            )
        yield "data: [DONE]\n\n"

    log.info("[CHAT_STREAM] msg_len=%d session=%s", len(req.message), req.session_id)
    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
def sessions():
    return agent.memory.list_sessions()


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return agent.memory.history(session_id, limit=200)
