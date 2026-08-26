"""Router: Chat e sessões."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agent.agent import PermissionDeniedError, StudyAgent

router = APIRouter(prefix="/api")

agent = StudyAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    use_screen: bool = False
    region: dict | None = None
    monitor: int = 1
    image_b64: str | None = None
    doc_id: str | None = None


@router.get("/health")
def health():
    return {"status": "ok", **agent.status()}


@router.post("/chat")
def chat(req: ChatRequest):
    try:
        if req.image_b64:
            from ..security.permissions import PermissionManager
            PermissionManager().require("camera")
        return agent.process(
            req.message,
            session_id=req.session_id,
            use_screen=req.use_screen,
            region=req.region,
            monitor=req.monitor,
            image_b64=req.image_b64,
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
