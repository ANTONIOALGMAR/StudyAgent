from app.core.vision_router import (
    MAX_OCR_CHARS,
    build_image_note,
    decide_ocr_block,
    format_window_note,
)
from app.vision.window import active_window


def test_nota_de_tela_com_monitor_e_tamanho():
    nota = build_image_note(camera=False, monitor=2, size=(1440, 900))
    assert "monitor 2" in nota
    assert "1440x900" in nota
    assert "NA IMAGEM" in nota


def test_nota_de_camera():
    nota = build_image_note(camera=True)
    assert "câmera" in nota
    assert "monitor" not in nota


def test_nota_sem_monitor_menciona_tela():
    assert "minha tela" in build_image_note(camera=False)


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
