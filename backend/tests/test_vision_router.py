from unittest.mock import MagicMock

from app.core.vision_router import (
    MAX_OCR_CHARS,
    VISION_SYSTEM_PROMPT,
    OCRResult,
    ScreenCaptureResult,
    VisionContext,
    VisionIntent,
    VisionRequest,
    build_image_note,
    decide_ocr_block,
    detect_vision_intent,
    format_window_note,
)
from app.vision.window import active_window

# ── VisionRequest ──────────────────────────────────────────────────


def test_vision_request_is_screen():
    req = VisionRequest(message="leia a tela", monitor=2)
    assert req.is_screen
    assert not req.is_camera


def test_vision_request_is_camera():
    req = VisionRequest(message="foto", camera_image_b64="abc", intent=VisionIntent.CAMERA)
    assert req.is_camera
    assert not req.is_screen


# ── ScreenCaptureResult ────────────────────────────────────────────


def test_screen_capture_result_from_valid_image():
    img = MagicMock()
    img.width = 1920
    img.height = 1080
    result = ScreenCaptureResult.from_image(img, monitor=1)
    assert result.is_valid
    assert result.width == 1920
    assert result.error is None


def test_screen_capture_result_failed():
    result = ScreenCaptureResult.failed(monitor=2, error="Wayland falhou")
    assert not result.is_valid
    assert result.error == "Wayland falhou"
    assert result.width == 0


# ── OCRResult ──────────────────────────────────────────────────────


def test_ocr_result_from_useful_text():
    texto = "x" * 100
    result = OCRResult.from_text(texto)
    assert result.is_useful
    assert result.char_count == 100


def test_ocr_result_from_short_text():
    result = OCRResult.from_text("pouco")
    assert not result.is_useful


def test_ocr_result_from_none():
    result = OCRResult.from_text(None)
    assert not result.is_useful
    assert result.char_count == 0


def test_ocr_result_failed():
    result = OCRResult.failed("Tesseract error")
    assert not result.is_useful
    assert result.error == "Tesseract error"


# ── VisionContext ──────────────────────────────────────────────────


def test_vision_context_has_ocr():
    ctx = VisionContext(source="screen", ocr_text="x" * 100)
    assert ctx.has_ocr


def test_vision_context_no_ocr_short():
    ctx = VisionContext(source="screen", ocr_text="pouco")
    assert not ctx.has_ocr


def test_vision_context_is_valid():
    ctx = VisionContext(source="screen", image_bytes=b"\x89PNG")
    assert ctx.is_valid


def test_vision_context_not_valid_no_image():
    ctx = VisionContext(source="screen", image_bytes=b"")
    assert not ctx.is_valid


def test_vision_context_not_valid_with_errors():
    ctx = VisionContext(source="screen", image_bytes=b"\x89PNG", errors=["falha"])
    assert not ctx.is_valid


# ── VisionIntent detection ─────────────────────────────────────────


def test_intent_screen_read():
    assert detect_vision_intent("leia o monitor 2") == VisionIntent.SCREEN_READ


def test_intent_screen_describe():
    assert detect_vision_intent("descreva o que está na tela") == VisionIntent.SCREEN_READ


def test_intent_screen_error():
    assert detect_vision_intent("tem um erro na tela") == VisionIntent.SCREEN_ERROR


def test_intent_screen_code():
    assert detect_vision_intent("o que tem de código na tela") == VisionIntent.SCREEN_CODE


def test_intent_screen_exercise():
    assert detect_vision_intent("qual exercício aparece na tela") == VisionIntent.SCREEN_EXERCISE


def test_intent_screen_question_default():
    assert detect_vision_intent("me mostre a tela") == VisionIntent.SCREEN_QUESTION


# ── Vision system prompt ───────────────────────────────────────────


def test_vision_system_prompt_forbids_greeting():
    assert "NUNCA dê saudação" in VISION_SYSTEM_PROMPT


def test_vision_system_prompt_is_short():
    assert len(VISION_SYSTEM_PROMPT.splitlines()) < 20


def test_vision_system_prompt_has_format():
    assert "O QUE VEJO" in VISION_SYSTEM_PROMPT
    assert "CONTEÚDO" in VISION_SYSTEM_PROMPT
    assert "ANÁLISE" in VISION_SYSTEM_PROMPT


# ── Legacy functions (backward compat) ─────────────────────────────


def test_nota_de_tela_com_monitor_e_tamanho():
    nota = build_image_note(camera=False, monitor=2, size=(1440, 900))
    assert "monitor 2" in nota
    assert "1440x900" in nota
    assert "CONTEÚDO VISUAL" in nota


def test_nota_de_camera():
    nota = build_image_note(camera=True)
    assert "câmera" in nota or "CÂMERA" in nota
    assert "monitor" not in nota


def test_nota_sem_monitor_menciona_tela():
    assert "tela" in build_image_note(camera=False)


def test_ocr_curto_nao_vira_bloco():
    assert decide_ocr_block("pouco") is None
    assert decide_ocr_block("") is None
    assert decide_ocr_block(None) is None


def test_ocr_denso_vira_bloco():
    bloco = decide_ocr_block("x" * 100)
    assert bloco.startswith("TEXTO DETECTADO POR OCR")
    assert "xxx" in bloco


def test_ocr_gigante_e_truncado():
    bloco = decide_ocr_block("a" * (MAX_OCR_CHARS + 500))
    assert "[…]" in bloco
    assert len(bloco) < MAX_OCR_CHARS + 200


def test_janela_none_nao_gera_nota():
    assert format_window_note(None) is None
    assert format_window_note({}) is None


def test_nota_de_janela_completa():
    nota = format_window_note({"app": "okular", "title": "Trigonometria.pdf"})
    assert "aplicativo: okular" in nota
    assert "janela: Trigonometria.pdf" in nota


def test_active_window_em_wayland_sem_ferramentas_retorna_none(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert active_window() is None
