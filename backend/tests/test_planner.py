from app.core.planner import build_plan
from app.core.vision_router import VisionIntent


def test_pergunta_sobre_tela_captura():
    p = build_plan("que questões aparecem na tela 2?", use_screen_requested=False)
    assert p.capture_screen
    assert p.monitor == 2


def test_monitor_por_extensao_na_mensagem():
    p = build_plan("leia o monitor 3", use_screen_requested=False)
    assert p.capture_screen and p.monitor == 3


def test_documento_tem_prioridade_sem_mencao_de_tela():
    p = build_plan(
        "resuma o documento",
        use_screen_requested=True,
        requested_doc_id="abc123",
    )
    assert p.wants_document
    assert not p.capture_screen


def test_documento_mas_pergunta_de_tela_captura():
    p = build_plan(
        "o que tem na tela 1?",
        use_screen_requested=True,
        requested_doc_id="abc123",
    )
    assert p.capture_screen
    assert p.wants_document


def test_sessao_lembra_documento_quando_intenção_de_doc():
    p = build_plan(
        "qual o valor do capítulo 7 do pdf?",
        use_screen_requested=False,
        session_doc_id="doc9",
    )
    assert p.doc_id == "doc9"


def test_sessao_nao_reativa_documento_sem_intencao():
    p = build_plan(
        "quanto é 2+2?",
        use_screen_requested=False,
        session_doc_id="doc9",
    )
    assert p.doc_id is None
    assert not p.capture_screen


def test_leitura_integral_palavras_chave():
    p = build_plan(
        "resuma tudo", use_screen_requested=False, requested_doc_id="d", doc_text_len=99999
    )
    assert p.whole_doc


def test_documento_pequeno_vai_inteiro():
    p = build_plan(
        "fale sobre isso",
        use_screen_requested=False,
        requested_doc_id="d",
        doc_text_len=500,
    )
    assert p.whole_doc


def test_documento_grande_sem_pedido_de_resumo_usa_trechos():
    p = build_plan(
        "qual a fórmula da questão 3?",
        use_screen_requested=False,
        requested_doc_id="d",
        doc_text_len=99999,
    )
    assert not p.whole_doc


# ── Vision intent detection ────────────────────────────────────────


def test_vision_intent_read_on_screen_keyword():
    p = build_plan("leia o monitor 1", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_READ


def test_vision_intent_error_on_screen():
    p = build_plan("tem um erro na tela", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_ERROR


def test_vision_intent_code_on_screen():
    p = build_plan("o que tem de código na tela 2", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_CODE


def test_vision_intent_exercise_on_screen():
    p = build_plan("qual exercício aparece na tela", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_EXERCISE


def test_vision_intent_default_when_no_screen():
    p = build_plan("quanto é 2+2?", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_QUESTION


def test_vision_intent_camera():
    p = build_plan("o que vê na foto?", use_screen_requested=False, camera_image=True)
    assert p.vision_intent == VisionIntent.CAMERA


def test_vision_intent_on_use_screen_requested():
    p = build_plan("o que tem na tela?", use_screen_requested=True)
    assert p.vision_intent == VisionIntent.SCREEN_READ
