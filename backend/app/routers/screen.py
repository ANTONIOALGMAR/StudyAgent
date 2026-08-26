"""Router: Captura e análise de tela."""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..agent.agent import PermissionDeniedError, StudyAgent
from ..security.permissions import PermissionManager
from ..vision.screen import image_to_base64, image_to_jpeg_base64, list_monitors

router = APIRouter(prefix="/api")
agent = StudyAgent()
permissions = PermissionManager()


class AnalyzeScreenRequest(BaseModel):
    question: str | None = None
    session_id: str | None = None
    region: dict | None = None
    monitor: int = 1


@router.post("/screen/capture")
def screen_capture(region: dict | None = None, monitor: int = 1):
    try:
        shot, info = agent.capture_and_read_screen(region=region, monitor=monitor)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"image_b64": base64.b64encode(image_to_base64(shot)).decode("ascii"), **info}


@router.get("/screen/monitors")
def screen_monitors():
    return {"monitors": list_monitors()}


@router.get("/screen/preview")
def screen_preview(monitor: int = 0):
    try:
        permissions.require("screen_capture")
        from ..vision import screen as _screen
        shot = _screen.capture(monitor=monitor)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    jpeg = image_to_jpeg_base64(shot)
    return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/screen/analyze")
def screen_analyze(req: AnalyzeScreenRequest):
    try:
        result = agent.analyze_screen(
            req.question, session_id=req.session_id, region=req.region, monitor=req.monitor,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return result
