from app.core.planner import IntentCategory, build_plan, detect_category
from app.core.vision_router import VisionIntent

# ── IntentCategory ─────────────────────────────────────────────────


def test_category_default_is_chat():
    p = build_plan("bom dia", use_screen_requested=False)
    assert p.category == IntentCategory.CHAT


def test_category_screen_when_capture():
    p = build_plan("o que tem na tela?", use_screen_requested=False)
    assert p.category == IntentCategory.SCREEN


def test_category_document():
    p = build_plan(
        "resuma o pdf",
        use_screen_requested=False,
        requested_doc_id="d1",
    )
    assert p.category == IntentCategory.DOCUMENT


def test_category_camera():
    p = build_plan(
        "o que vê na foto?",
        use_screen_requested=False,
        camera_image=True,
    )
    assert p.category == IntentCategory.CAMERA


def test_category_web_search():
    p = build_plan("busque notícias sobre IA", use_screen_requested=False)
    assert p.category == IntentCategory.WEB_SEARCH


def test_category_calculate():
    p = build_plan("quanto é 2+2?", use_screen_requested=False)
    assert p.category == IntentCategory.CALCULATE


def test_category_system_action():
    p = build_plan("abra o navegador", use_screen_requested=False)
    assert p.category == IntentCategory.SYSTEM_ACTION


def test_detect_category_document_priority():
    assert detect_category(
        "busque isso no doc",
        capture_screen=False,
        camera_image=False,
        wants_document=True,
    ) == IntentCategory.DOCUMENT


def test_detect_category_camera_priority():
    assert detect_category(
        "busque isso",
        capture_screen=False,
        camera_image=True,
        wants_document=False,
    ) == IntentCategory.CAMERA


def test_detect_category_screen_priority():
    assert detect_category(
        "busque isso",
        capture_screen=True,
        camera_image=False,
        wants_document=False,
    ) == IntentCategory.SCREEN


# ── human_monitor (V3) ─────────────────────────────────────────────


def test_human_monitor_tela():
    p = build_plan("leia a tela 2", use_screen_requested=False)
    assert p.human_monitor == 2
    # tela 2 → índice interno 1
    assert p.monitor == 1


def test_human_monitor_monitor():
    p = build_plan("leia o monitor 0", use_screen_requested=False)
    assert p.human_monitor == 0
    assert p.monitor == 0


def test_human_monitor_none_when_not_specified():
    p = build_plan("quanto é 2+2?", use_screen_requested=False)
    assert p.human_monitor is None


# ── vision_intent via plan (V3 aliado) ─────────────────────────────


def test_plan_vision_intent_compare():
    p = build_plan("compare as telas 2 e 3", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_COMPARE


def test_plan_vision_intent_analyze():
    p = build_plan("analise a tela 1", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_ANALYZE


def test_plan_vision_intent_monitor():
    p = build_plan("em qual tela vai aparecer?", use_screen_requested=False)
    assert p.vision_intent == VisionIntent.SCREEN_MONITOR
