"""Router: Reconhecimento facial de usuário via modelo de visão."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..security.permissions import PermissionManager
from ..tutor import profile as student_profile
from ..vision.facial import FaceRecognition

router = APIRouter(prefix="/api/face")
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
def face_present(req: FaceImageRequest):
    """Detecta se há rosto claro na imagem (sem casar com identidade)."""
    data = _decode_image(req.image_b64)
    try:
        return recognition.recognize(data, threshold=2.0)
    except Exception as exc:
        log.exception("[FACIAL] present falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/register")
def face_register(req: FaceRegisterRequest):
    """Cadastra o rosto atual da câmera como identidade do usuário."""
    data = _decode_image(req.image_b64)
    try:
        result = recognition.register(req.name, data)
        student_profile.sync_profile_name(req.name)
        permissions.set("camera", True, reason="usuário identificado com sucesso")
        permissions.set("screen_capture", True, reason="usuário identificado com sucesso")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("[FACIAL] register falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/recognize")
def face_recognize(req: FaceImageRequest):
    """Identifica o usuário comparando com as faces cadastradas."""
    data = _decode_image(req.image_b64)
    try:
        result = recognition.recognize(data)
        if result.get("name"):
            student_profile.sync_profile_name(result["name"])
            permissions.set("camera", True, reason="usuário identificado com sucesso")
            permissions.set("screen_capture", True, reason="usuário identificado com sucesso")
        return result
    except Exception as exc:
        log.exception("[FACIAL] recognize falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/list")
def face_list():
    return {"faces": recognition.list_faces()}


@router.delete("/{name}")
def face_delete(name: str):
    if not recognition.delete(name):
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"deleted": name}
