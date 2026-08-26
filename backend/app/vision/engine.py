"""Vision Engine — Processador puro de dados visuais.

Coordena OCR e detecção de janela. NÃO faz chamadas LLM —
isso fica a cargo do agente via _run_tool_loop.
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import Image

from ..core.vision_router import VisionContext
from ..vision import ocr

log = logging.getLogger("studyagent.vision")


def process_capture(
    shot: Image.Image,
    monitor_id: int,
    window_info: Optional[dict] = None,
) -> VisionContext:
    """Processa captura de tela: OCR + contexto de janela → VisionContext.

    Processador puro — sem chamadas LLM. O agente usa o image_bytes
    para enviar ao modelo de visão.
    """
    from ..vision.screen import image_to_base64

    # OCR
    ocr_result = ocr.read_text_structured(shot)
    stages = ["CAPTURED"]
    errors = []

    if ocr_result.error:
        log.warning("[VISION] ocr_warning=%s", ocr_result.error)
        stages.append("OCR_WARNING")
    elif ocr_result.is_useful:
        stages.append("OCR_COMPLETED")
        log.info("[VISION] ocr_completed chars=%d", ocr_result.char_count)
    else:
        stages.append("OCR_NO_TEXT")
        log.info("[VISION] ocr_no_text chars=%d", ocr_result.char_count)

    # Contexto de janela
    if window_info:
        stages.append("WINDOW_CHECKED")

    # Construir VisionContext
    image_bytes = image_to_base64(shot)
    ctx = VisionContext(
        source="screen",
        monitor_id=monitor_id,
        resolution=(shot.width, shot.height),
        ocr_text=ocr_result.text if ocr_result.is_useful else None,
        window_app=window_info.get("app") if window_info else None,
        window_title=window_info.get("title") if window_info else None,
        image_bytes=image_bytes,
        pipeline_stages=stages,
        errors=errors,
    )

    log.info("[VISION] context_built has_ocr=%s window=%s",
             ctx.has_ocr, window_info.get("app") if window_info else None)

    return ctx
