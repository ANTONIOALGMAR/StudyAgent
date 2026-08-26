"""Router: Chat e sessões."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..agent.agent import PermissionDeniedError, StudyAgent

router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)

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
        return agent.process(
            req.message,
            session_id=req.session_id,
            use_screen=req.use_screen,
            region=req.region,
            monitor=req.monitor,
            camera_image=req.camera_image,
            doc_id=req.doc_id,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/sessions")
def sessions():
    return agent.memory.list_sessions()


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return agent.memory.history(session_id, limit=200)
