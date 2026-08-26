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


@router.get("/screen/diagnostics")
def screen_diagnostics():
    import os
    import time

    from ..core.model_manager import resolve
    from ..vision import ocr as _ocr

    monitors = list_monitors()
    ocr_avail = _ocr.available()
    vision_model = resolve("vision")
    ollama_ok = False
    vision_test = False
    vision_test_time_ms = None
    capture_test = False
    capture_test_time_ms = None
    ocr_test = False
    ocr_test_time_ms = None

    # Teste real de captura de tela
    try:
        from ..security.permissions import PermissionManager as _PM
        _PM().require("screen_capture")
        t0 = time.monotonic()
        from ..vision import screen as _screen
        shot = _screen.capture(monitor=0)
        capture_test_time_ms = int((time.monotonic() - t0) * 1000)
        capture_test = shot is not None and shot.width > 0 and shot.height > 0
    except Exception:
        capture_test = False

    # Teste real de OCR
    if capture_test and ocr_avail:
        try:
            t0 = time.monotonic()
            _ocr.read_text_structured(shot)
            ocr_test_time_ms = int((time.monotonic() - t0) * 1000)
            ocr_test = True  # Tesseract respondeu (mesmo que texto vazio)
        except Exception:
            ocr_test = False

    # Teste real de modelo de visão
    try:
        import ollama as _ollama
        _ollama.list()
        ollama_ok = True
        from PIL import Image
        test_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        from ..vision.screen import image_to_base64 as _i2b
        test_b64 = base64.b64encode(_i2b(test_img)).decode()
        t0 = time.monotonic()
        resp = _ollama.chat(
            model=vision_model,
            messages=[{"role": "user", "content": "Describe this image in one word.", "images": [test_b64]}],
            options={"num_predict": 10},
        )
        vision_test_time_ms = int((time.monotonic() - t0) * 1000)
        vision_test = bool(resp.get("message", {}).get("content"))
    except Exception:
        pass

    perm = PermissionManager()
    return {
        "screen_capture": capture_test,
        "capture_time_ms": capture_test_time_ms,
        "monitor_count": len(monitors),
        "monitors": monitors,
        "ocr_available": ocr_avail,
        "ocr_test": ocr_test,
        "ocr_time_ms": ocr_test_time_ms,
        "tesseract_path": os.popen("which tesseract 2>/dev/null").read().strip() or None,
        "vision_model": vision_model,
        "ollama_available": ollama_ok,
        "vision_test": vision_test,
        "vision_time_ms": vision_test_time_ms,
        "permissions": {
            "screen": perm.all().get("screen_capture", False),
            "camera": perm.all().get("camera", False),
        },
    }
