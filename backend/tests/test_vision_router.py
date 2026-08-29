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
    req = VisionRequest(message="leia a tela", monitor_id=2)
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
    result = ScreenCaptureResult.from_image(img, monitor_id=1)
    assert result.is_valid
    assert result.width == 1920
    assert result.error is None


def test_screen_capture_result_failed():
    result = ScreenCaptureResult.failed(monitor_id=2, error="Wayland falhou")
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


def test_intent_screen_show_returns_read():
    # "mostre" é verbo de análise → lê a tela
    assert detect_vision_intent("me mostre a tela") == VisionIntent.SCREEN_READ


def test_intent_screen_describe_default():
    # sem verbos/refs explícitas cai em descrição
    assert detect_vision_intent("isso aí") == VisionIntent.SCREEN_DESCRIBE


def test_intent_screen_compare():
    assert detect_vision_intent("compare as telas 1 e 2") == VisionIntent.SCREEN_COMPARE


def test_intent_screen_compare_difference():
    assert detect_vision_intent("qual a diferença entre os monitores") == VisionIntent.SCREEN_COMPARE


def test_intent_screen_monitor_selection():
    assert detect_vision_intent("em qual monitor vai aparecer?") == VisionIntent.SCREEN_MONITOR


def test_intent_screen_monitor_active():
    assert detect_vision_intent("qual monitor está ativo?") == VisionIntent.SCREEN_MONITOR


def test_intent_screen_analyze():
    assert detect_vision_intent("analise o monitor 1") == VisionIntent.SCREEN_ANALYZE


def test_intent_screen_analyze_inspect():
    assert detect_vision_intent("inspecione a tela 3") == VisionIntent.SCREEN_ANALYZE


def test_intent_code_still_prioritized_over_analyze():
    assert detect_vision_intent("analise o código da tela") == VisionIntent.SCREEN_CODE


# ── VisionContext V3 ───────────────────────────────────────────────


def test_vision_context_v3_fields_defaults():
    ctx = VisionContext(source="screen")
    assert ctx.human_monitor is None
    assert ctx.physical_monitor_name is None
    assert ctx.position is None
    assert ctx.ocr_confidence is None


def test_vision_context_v3_vision_intent_alias():
    ctx = VisionContext(source="screen", intent=VisionIntent.SCREEN_COMPARE)
    assert ctx.vision_intent == "SCREEN_COMPARE"


def test_vision_context_v3_fields_set():
    ctx = VisionContext(
        source="screen",
        monitor_id=1,
        human_monitor=2,
        physical_monitor_name="HDMI-A-1",
        position={"left": 0, "top": 0, "width": 1920, "height": 1080},
        ocr_confidence=0.9,
        intent=VisionIntent.SCREEN_ANALYZE,
    )
    assert ctx.human_monitor == 2
    assert ctx.physical_monitor_name == "HDMI-A-1"
    assert ctx.position["width"] == 1920
    assert ctx.ocr_confidence == 0.9


def test_vision_context_prompt_evidence_first():
    ctx = VisionContext(
        source="screen",
        monitor_id=1,
        human_monitor=2,
        physical_monitor_name="HDMI-A-1",
        position={"left": 0, "top": 0, "width": 1920, "height": 1080},
        ocr_text="x" * 100,
        window_app="okular",
        user_question="qual a resposta?",
        ocr_confidence=1.0,
    )
    prompt = ctx.prompt_context()
    # EvidenceFirst: separa EVIDÊNCIA de INFERÊNCIA
    assert "EVIDÊNCIA" in prompt
    assert "INFERÊNCIA" in prompt
    assert "HDMI-A-1" in prompt
    assert "MONITOR (número humano" in prompt
    assert "POSIÇÃO NO DESKTOP VIRTUAL" in prompt
    assert "CONFIANÇA DO OCR" in prompt


# ── Vision system prompt ───────────────────────────────────────────


def test_vision_system_prompt_forbids_greeting():
    assert "NUNCA comece com" in VISION_SYSTEM_PROMPT
    assert "Olá" in VISION_SYSTEM_PROMPT


def test_vision_system_prompt_is_vision_role():
    assert "VISÃO" in VISION_SYSTEM_PROMPT
    assert len(VISION_SYSTEM_PROMPT.splitlines()) > 20


def test_vision_system_prompt_has_format():
    assert "O QUE VEJO" in VISION_SYSTEM_PROMPT
    assert "CONTEÚDO" in VISION_SYSTEM_PROMPT
    assert "ANÁLISE" in VISION_SYSTEM_PROMPT


# ── Legacy functions (backward compat) ─────────────────────────────


def test_nota_de_tela_com_monitor_e_tamanho():
    nota = build_image_note(camera=False, monitor=2, size=(1440, 900))
    assert "monitor 2" in nota
    assert "1440x900" in nota
    assert "CAPTURA REAL DE TELA" in nota


def test_nota_de_camera():
    nota = build_image_note(camera=True)
    assert "câmera" in nota or "CÂMERA" in nota
    assert "monitor" not in nota


def test_nota_sem_monitor_menciona_tela():
    assert "TELA" in build_image_note(camera=False)


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
