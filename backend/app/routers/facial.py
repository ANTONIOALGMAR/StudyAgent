"""Router: Reconhecimento facial de usuário via modelo de visão."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..agent.agent import PermissionDeniedError
from ..security.permissions import PermissionManager
from ..vision.facial import FaceRecognition

router = APIRouter(prefix="/api/face")
limiter = Limiter(key_func=get_remote_address)
permissions = PermissionManager()
recognition = FaceRecognition()
log = logging.getLogger("studyagent.router.facial")


class FaceRegisterRequest(BaseModel):
    name: str
    image_b64: str


class FaceImageRequest(BaseModel):
    image_b64: str


def _decode_image(image_b64: str) -> bytes:
    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        return base64.b64decode(image_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Imagem inválida (esperava base64).") from exc


@router.post("/present")
@limiter.limit("30/minute")
def face_present(request: Request, req: FaceImageRequest):
    """Detecta se há rosto claro na imagem (sem casar com identidade)."""
    try:
        permissions.require("camera")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    data = _decode_image(req.image_b64)
    try:
        return recognition.recognize(data, threshold=2.0)
    except Exception as exc:
        log.exception("[FACIAL] present falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/register")
@limiter.limit("10/minute")
def face_register(request: Request, req: FaceRegisterRequest):
    """Cadastra o rosto atual da câmera como identidade do usuário."""
    try:
        permissions.require("camera")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    data = _decode_image(req.image_b64)
    try:
        return recognition.register(req.name, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("[FACIAL] register falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/recognize")
@limiter.limit("30/minute")
def face_recognize(request: Request, req: FaceImageRequest):
    """Identifica o usuário comparando com as faces cadastradas."""
    try:
        permissions.require("camera")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    data = _decode_image(req.image_b64)
    try:
        return recognition.recognize(data)
    except Exception as exc:
        log.exception("[FACIAL] recognize falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/list")
def face_list():
    try:
        permissions.require("camera")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"faces": recognition.list_faces()}


@router.delete("/{name}")
def face_delete(name: str):
    try:
        permissions.require("camera")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not recognition.delete(name):
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"deleted": name}
