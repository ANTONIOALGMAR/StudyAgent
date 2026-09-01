"""Motor de percepção visual.

Responsabilidade:
captura processada → OCR → contexto visual.

Não chama o LLM. V2: cache de visão para evitar reprocessamento.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from PIL import Image

from ..core.cache import image_hash, vision_cache
from ..core.vision_router import VisionContext, VisionIntent
from ..vision import ocr

log = logging.getLogger("studyagent.vision")


def process_capture(
    shot: Image.Image,
    monitor_id: int,
    window_info: Optional[dict] = None,
    *,
    user_question: str = "",
    intent: VisionIntent = VisionIntent.SCREEN_QUESTION,
) -> VisionContext:
    """Processa captura de tela: OCR + contexto de janela → VisionContext.

    Processador puro — sem chamadas LLM. O agente usa o image_bytes
    para enviar ao modelo de visão. V2: cache de resultados.
    """
    from ..vision.screen import image_to_base64

    # ── Cache check ──────────────────────────────────────────────
    try:
        img_bytes_raw = shot.tobytes()
        cache_key = hashlib.sha256(
            f"{image_hash(img_bytes_raw)}:{monitor_id}:{user_question[:100]}".encode()
        ).hexdigest()[:32]
        cached = vision_cache.get(cache_key)
        if cached is not None:
            log.info("[VISION] cache_hit monitor=%s", monitor_id)
            return cached
    except Exception:
        cache_key = None

    stages = ["CAPTURED"]
    errors: list[str] = []

    # ── OCR ─────────────────────────────────────────────────────────
    try:
        ocr_result = ocr.read_text_structured(shot)
    except Exception as exc:
        log.exception("Falha no OCR")
        ocr_result = None
        errors.append(f"OCR falhou: {exc}")

    if ocr_result:
        if ocr_result.error:
            stages.append("OCR_WARNING")
            log.warning("[VISION] OCR warning=%s", ocr_result.error)
        elif ocr_result.is_useful:
            stages.append("OCR_COMPLETED")
            log.info("[VISION] OCR completed chars=%d", ocr_result.char_count)
        else:
            stages.append("OCR_NO_TEXT")

    # ── JANELA ──────────────────────────────────────────────────────
    if window_info:
        stages.append("WINDOW_CHECKED")

    # ── SERIALIZAÇÃO DA IMAGEM ──────────────────────────────────────
    try:
        image_bytes = image_to_base64(shot)
    except Exception as exc:
        errors.append(f"Falha ao serializar imagem: {exc}")
        return VisionContext(
            source="screen",
            monitor_id=monitor_id,
            resolution=(shot.width, shot.height),
            user_question=user_question,
            intent=intent,
            pipeline_stages=stages,
            errors=errors,
        )

    if not image_bytes:
        errors.append("Imagem serializada ficou vazia")

    # ── CONTEXTO FINAL ──────────────────────────────────────────────
    ocr_text = (
        ocr_result.text
        if ocr_result and ocr_result.text
        else ""
    )

    # V3 — proxy de confiança do OCR: 1.0 se houver texto útil,
    # 0.5 se houver texto mínimo, 0.0 se ausente.
    ocr_conf = None
    if ocr_result is not None and ocr_result.text:
        ocr_conf = (
            1.0
            if ocr_result.is_useful
            else 0.5
        )
    else:
        ocr_conf = 0.0

    ctx = VisionContext(
        source="screen",
        monitor_id=monitor_id,
        resolution=(shot.width, shot.height),
        ocr_text=ocr_text,
        ocr_confidence=ocr_conf,
        window_app=window_info.get("app") if window_info else None,
        window_title=window_info.get("title") if window_info else None,
        image_bytes=image_bytes,
        user_question=user_question,
        intent=intent,
        pipeline_stages=stages,
        errors=errors,
        vision_confidence=1.0 if image_bytes else 0.0,
    )

    # Tentativa de executar um detector de objetos estruturado, se disponível.
    # Não é obrigatório: o projeto pode não fornecer um detector local — nesse
    # caso a import falhará e a execução prossegue normalmente.
    try:
        # detect_image(shot) deve retornar uma lista de detecções com:
        # [{"label": "celular", "confidence": 0.88, "bbox": {"left": 10, "top": 20, "width": 100, "height": 80}}, ...]
        from ..vision import detector as _detector  # type: ignore

        detections = None
        try:
            detections = _detector.detect_image(shot)
        except Exception as _exc:
            # se o detector falhar internamente, logamos em debug e seguimos
            log.debug("[VISION] detector execution failed: %s", _exc)
            detections = None

        if detections:
            # guardamos na metadata para que o orquestrador/agent possam
            # optar por consumir as detecções estruturadas.
            ctx.metadata["detections"] = detections
            ctx.add_stage("DETECTIONS")
            log.info("[VISION] detections=%d", len(detections))
    except Exception as exc:
        # ImportError ou outros — detector ausente ou não compatível.
        log.debug("[VISION] detector unavailable or failed to import: %s", exc)

    if ctx.is_valid:
        stages.append("CONTEXT_BUILT")
        log.info("[VISION] context_built monitor=%s image_bytes=%d ocr=%s",
                 monitor_id, len(image_bytes), ctx.has_ocr)

    # ── Cache store ──────────────────────────────────────────────
    if cache_key and ctx.is_valid:
        vision_cache.set(cache_key, ctx)

    return ctx
