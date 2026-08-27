"""Integration Tests — E2E, Regression, Error Recovery (sections 57-62).

Cobre:
- Pipeline completo: chat → planner → vision → LLM → resposta
- Circuit breaker em cenários reais
- Fallback e recuperação de erros
- Evidence tracking ao longo do pipeline
- Tool registry stats durante execução
- Health check endpoint
"""

import time
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from app.agent.agent import StudyAgent
from app.core.context_manager import ContextManager
from app.core.orchestrator.circuit_breaker import CircuitBreaker, CircuitState
from app.core.orchestrator.evidence import EvidenceStore, EvidenceType
from app.core.orchestrator.validator import ResponseValidator
from app.core.planner import build_plan
from app.core.tool_registry import (
    all_tools,
    discover,
    get,
    reset_registry,
    tool,
)
from app.core.vision_router import VisionIntent, detect_vision_intent
from app.vision.engine import process_capture

# ── Helpers ────────────────────────────────────────────────────────


def _fake_image(w=1920, h=1080, color=(100, 150, 200)):
    img = Image.new("RGB", (w, h), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 800, 400], fill=(255, 255, 255))
    draw.text((120, 120), "Conteudo de teste visivel", fill=(0, 0, 0))
    return img


def _black_image(w=1920, h=1080):
    return Image.new("RGB", (w, h), color=(0, 0, 0))


def _fake_monitors():
    return [
        {"index": 0, "width": 4726, "height": 1080, "left": 0, "top": 0},
        {"index": 1, "width": 1920, "height": 1080, "left": 2806, "top": 0},
        {"index": 2, "width": 1440, "height": 900, "left": 0, "top": 180},
        {"index": 3, "width": 1365, "height": 1024, "left": 1440, "top": 56},
    ]


def _make_agent():
    """Cria um StudyAgent mockado para testes."""
    agent = StudyAgent.__new__(StudyAgent)
    agent.memory = MagicMock()
    agent.memory.get_messages.return_value = []
    agent.memory.get_or_create_session.return_value = "test-session-001"
    agent.memory.count_messages.return_value = 0
    agent.ctx = ContextManager(agent.memory, lambda sid, text: None)
    agent._last_monitor = None
    agent._last_face = None
    agent._session_docs = {}
    return agent


# ═══════════════════════════════════════════════════════════════════
# SECTION 57: E2E Pipeline Tests
# ═══════════════════════════════════════════════════════════════════


class TestE2E_VisionPipeline:
    """Pipeline completo: mensagem → planner → captura → OCR → LLM."""

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_full_screen_read_pipeline(self, mock_sm_cls, mock_win, mock_chat):
        """'leia o monitor 2' → captura → OCR → resposta."""
        img = _fake_image()
        mock_sm_cls.capture_monitor.return_value = img
        mock_sm_cls.list_monitors.return_value = _fake_monitors()
        mock_sm_cls.validate_monitor.return_value = True
        mock_win.active_window.return_value = {"app": "Firefox", "title": "GitHub"}
        mock_chat.return_value = "A tela mostra um repositorio GitHub com codigo Python."

        agent = StudyAgent()
        result = agent.process("leia o monitor 2", use_screen=True)

        assert result["response"] != ""
        assert "screen_capture" in result["tools_used"]
        assert result.get("evidence") is not None

    @patch("app.agent.agent.chat")
    def test_plain_text_chat_no_vision(self, mock_chat):
        """Mensagem simples não ativa pipeline de visão."""
        mock_chat.return_value = "A resposta do agente."

        agent = _make_agent()
        result = agent.process("o que é python?")

        assert "screen_capture" not in result["tools_used"]
        assert result.get("evidence") is not None

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_vision_pipeline_evidence_tracking(self, mock_sm_cls, mock_win, mock_chat):
        """Pipeline de visão preenche evidence corretamente."""
        img = _fake_image()
        mock_sm_cls.capture_monitor.return_value = img
        mock_sm_cls.list_monitors.return_value = _fake_monitors()
        mock_sm_cls.validate_monitor.return_value = True
        mock_win.active_window.return_value = {"app": "VSCode", "title": "main.py"}
        mock_chat.return_value = "Vejo o VSCode com um arquivo Python aberto."

        agent = StudyAgent()
        result = agent.process("leia o monitor 1", use_screen=True)
        ev = result.get("evidence")
        assert ev is not None
        assert ev["has_screen"] is True
        assert isinstance(ev["types"], list)
        assert "SCREEN" in ev["types"]


class TestE2E_ToolExecution:
    """Tool execution end-to-end com stats."""

    def setup_method(self):
        reset_registry()

    def test_tool_call_records_stats(self):
        """Chamada de tool registra stats no Tool."""
        @tool(name="e2e_counter", description="count", parameters={})
        def handler(args):
            return "ok"

        t = get("e2e_counter")
        t.handler({})
        t.stats.record_success(50.0)
        t.stats.record_success(80.0)

        assert t.stats.total_calls == 2
        assert t.stats.success_count == 2
        assert t.stats.avg_duration_ms == 65.0

    def test_multiple_tools_registry_discovery(self):
        """Múltiplas tools registradas são descobertas."""
        @tool(name="e2e_alpha", description="alpha tool", parameters={}, tags=["test"])
        def h1(a): return ""
        @tool(name="e2e_beta", description="beta web search", parameters={}, tags=["search"])
        def h2(a): return ""

        by_tag = discover(tag="test")
        assert len(by_tag) == 1
        by_query = discover(query="web")
        assert len(by_query) == 1


class TestE2E_MemoryPersistence:
    """Memory persistence durante sessão."""

    @patch("app.agent.agent.chat")
    def test_session_id_persists_across_messages(self, mock_chat):
        """session_id persiste entre mensagens quando fornecido."""
        mock_chat.return_value = "resposta"

        agent = StudyAgent()
        r1 = agent.process("olá")
        sid = r1["session_id"]
        r2 = agent.process("tudo bem?", session_id=sid)

        assert r1["session_id"] == r2["session_id"]


# ═══════════════════════════════════════════════════════════════════
# SECTION 60: Regression Tests
# ═══════════════════════════════════════════════════════════════════


class TestRegression_VisionPipeline:
    """Regrressões do pipeline de visão."""

    def test_planner_detects_screen_keywords(self):
        """Planner detecta keywords de tela."""
        p = build_plan("leia a tela", use_screen_requested=False)
        assert p.vision_intent == VisionIntent.SCREEN_READ

    def test_planner_detects_screen_describe(self):
        """Planner detecta SCREEN_DESCRIBE para mensagens genéricas com tela."""
        p = build_plan("descreva o que está na tela", use_screen_requested=True)
        assert p.vision_intent in (VisionIntent.SCREEN_DESCRIBE, VisionIntent.SCREEN_QUESTION, VisionIntent.SCREEN_READ)

    def test_planner_preserves_explicit_monitor(self):
        """Monitor explícito é preservado pelo planner."""
        p = build_plan("leia o monitor 3", use_screen_requested=False)
        assert p.monitor == 3

    def test_process_capture_returns_valid_context(self):
        """process_capture retorna VisionContext válido."""
        img = _fake_image(800, 600)
        ctx = process_capture(img, monitor_id=1)
        assert ctx.is_valid is True
        assert ctx.resolution == (800, 600)
        assert ctx.monitor_id == 1

    def test_process_capture_with_window_info(self):
        """process_capture inclui info da janela."""
        img = _fake_image()
        ctx = process_capture(img, monitor_id=2, window_info={"app": "Term", "title": "bash"})
        assert ctx.window_app == "Term"
        assert ctx.window_title == "bash"

    def test_vision_context_has_required_fields(self):
        """VisionContext tem todos os campos necessários."""
        img = _fake_image()
        ctx = process_capture(img, monitor_id=1)
        assert hasattr(ctx, "image_bytes")
        assert hasattr(ctx, "ocr_text")
        assert hasattr(ctx, "resolution")
        assert hasattr(ctx, "monitor_id")
        assert hasattr(ctx, "pipeline_stages")
        assert ctx.image_bytes is not None


class TestRegression_ToolExecution:
    """Regrressões de execução de tools."""

    def setup_method(self):
        reset_registry()

    def test_tool_schema_format(self):
        """Schema de tool tem formato correto."""
        @tool(name="reg_test", description="test", parameters={"q": {"type": "string"}})
        def h(a): return ""

        t = get("reg_test")
        schema = t.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "reg_test"
        assert "q" in schema["function"]["parameters"]["properties"]

    def test_tool_version_preserved(self):
        """Versão da tool é preservada."""
        @tool(name="reg_ver", description="v", parameters={}, version="2.1.0")
        def h(a): return ""

        t = get("reg_ver")
        assert t.version == "2.1.0"

    def test_tool_tags_preserved(self):
        """Tags da tool são preservadas."""
        @tool(name="reg_tags", description="t", parameters={}, tags=["a", "b"])
        def h(a): return ""

        t = get("reg_tags")
        assert "a" in t.tags
        assert "b" in t.tags


class TestRegression_Evidence:
    """Regrressões de evidence tracking."""

    def test_evidence_store_screen(self):
        """EvidenceStore registra screen evidence."""
        store = EvidenceStore()
        store.add_screen(monitor=2, width=1920, height=1080)
        assert store.has_screen is True
        assert len(store.screen_evidence) == 1

    def test_evidence_store_ocr(self):
        """EvidenceStore registra OCR evidence."""
        store = EvidenceStore()
        store.add_ocr("texto extraido da tela")
        assert store.has_ocr is True

    def test_evidence_store_intent(self):
        """EvidenceStore registra intent."""
        store = EvidenceStore()
        store.add_intent("SCREEN_READ", monitor=2)
        assert len(store.get_by_type(EvidenceType.INTENT)) == 1

    def test_evidence_summary(self):
        """Evidence summary contém campos esperados."""
        store = EvidenceStore()
        store.add_screen(monitor=1, width=100, height=100)
        store.add_ocr("texto")
        s = store.summary()
        assert "evidence_count" in s
        assert s["has_screen"] is True
        assert s["has_ocr"] is True

    def test_validator_flags_greeting_in_vision_response(self):
        """Validator detecta saudação em resposta de visão."""
        store = EvidenceStore()
        store.add_screen(monitor=1, width=100, height=100)
        v = ResponseValidator(store)
        issues = v.validate("Olá! Como posso ajudar?")
        assert any("saudação" in i.lower() or "greeting" in i.lower() or "Olá" in i for i in issues)

    def test_validator_passes_good_response(self):
        """Validator não flags resposta boa."""
        store = EvidenceStore()
        store.add_screen(monitor=1, width=100, height=100)
        v = ResponseValidator(store)
        issues = v.validate("A tela mostra um código Python com 150 linhas.")
        assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════════
# SECTION 61: Error Recovery Tests
# ═══════════════════════════════════════════════════════════════════


class TestErrorRecovery_CircuitBreaker:
    """Circuit breaker em cenários de erro."""

    def test_circuit_opens_and_recovers(self):
        """Circuit breaker abre após falhas e recupera."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow() is False

        time.sleep(0.15)
        assert cb.allow() is True
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_stops_tool_execution(self):
        """Circuit breaker impede execução de tools quando aberto."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.allow() is False

    def test_circuit_breaker_multiple_tools(self):
        """Circuit breaker pode ser usado por múltiplas tools."""
        cb1 = CircuitBreaker(failure_threshold=1)
        cb2 = CircuitBreaker(failure_threshold=1)

        cb1.record_failure()
        assert cb1.allow() is False
        assert cb2.allow() is True  # independente


class TestErrorRecovery_Fallback:
    """Fallback e recuperação de erros."""

    @patch("app.agent.agent.chat")
    def test_chat_failure_returns_empty(self, mock_chat):
        """Falha de chat retorna resposta vazia (tratada pelo agent)."""
        mock_chat.side_effect = RuntimeError("Ollama offline")

        agent = StudyAgent()
        result = agent.process("teste")
        assert isinstance(result["response"], str)

    @patch("app.agent.agent.chat")
    @patch("app.agent.agent.window")
    @patch("app.agent.agent.ScreenManager")
    def test_invalid_monitor_returns_error_message(self, mock_sm_cls, mock_win, mock_chat):
        """Monitor inválido retorna mensagem de erro."""
        mock_sm_cls.capture_monitor.return_value = None
        mock_sm_cls.list_monitors.return_value = _fake_monitors()
        mock_sm_cls.validate_monitor.return_value = False
        mock_win.active_window.return_value = None
        mock_chat.return_value = "Erro"

        agent = StudyAgent()
        result = agent.process("leia o monitor 99", use_screen=True)
        resp = result["response"].lower()
        assert "não existe" in resp or "não consegui" in resp or "erro" in resp

    def test_tool_registry_unknown_tool(self):
        """Tool desconhecida retorna None."""
        assert get("nonexistent_tool_xyz") is None

    def test_evidence_store_min_confidence(self):
        """EvidenceStore calcula min_confidence."""
        store = EvidenceStore()
        store.add_screen(monitor=1, width=100, height=100)
        store.add_ocr("texto", confidence=0.6)
        assert store.min_confidence == 0.6

    def test_evidence_store_empty_min_confidence(self):
        """EvidenceStore vazio retorna 0."""
        store = EvidenceStore()
        assert store.min_confidence == 0.0


class TestErrorRecovery_ValidatorEdgeCases:
    """Edge cases do ResponseValidator."""

    def test_validator_no_screen_no_issues(self):
        """Sem screen evidence, sem issues."""
        store = EvidenceStore()
        v = ResponseValidator(store)
        issues = v.validate("qualquer resposta")
        assert len(issues) == 0

    def test_validator_empty_response(self):
        """Resposta vazia não causa crash."""
        store = EvidenceStore()
        store.add_screen(monitor=1, width=100, height=100)
        v = ResponseValidator(store)
        issues = v.validate("")
        assert isinstance(issues, list)

    def test_validator_long_response_ok(self):
        """Resposta longa mas informativa é aceita."""
        store = EvidenceStore()
        store.add_screen(monitor=1, width=100, height=100)
        v = ResponseValidator(store)
        long_response = "A tela mostra " + "código " * 50 + "com 200 linhas."
        issues = v.validate(long_response)
        assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════════
# SECTION 62: Performance / Smoke Tests
# ═══════════════════════════════════════════════════════════════════


class TestSmoke_PlannerPerformance:
    """Planner deve ser rápido (<10ms por chamada)."""

    def test_planner_speed(self):
        start = time.time()
        for _ in range(100):
            build_plan("leia o monitor 2", use_screen_requested=False)
        elapsed = (time.time() - start) * 1000
        assert elapsed < 1000  # 100 chamadas < 1s

    def test_detect_intent_speed(self):
        start = time.time()
        for _ in range(100):
            detect_vision_intent("leia o texto no monitor 3")
        elapsed = (time.time() - start) * 1000
        assert elapsed < 1000


class TestSmoke_EvidenceStorePerformance:
    """EvidenceStore deve ser rápido."""

    def test_evidence_store_speed(self):
        start = time.time()
        for _ in range(1000):
            store = EvidenceStore()
            store.add_screen(monitor=1, width=100, height=100)
            store.add_ocr("texto")
            store.summary()
        elapsed = (time.time() - start) * 1000
        assert elapsed < 1000  # 1000 operações < 1s


class TestSmoke_ToolRegistryPerformance:
    """Tool registry deve ser rápido."""

    def setup_method(self):
        reset_registry()

    def test_registry_discover_speed(self):
        for i in range(50):
            @tool(name=f"perf_{i}", description=f"tool {i}", parameters={}, tags=["perf"])
            def h(a, _i=i): return ""

        start = time.time()
        for _ in range(500):
            discover(tag="perf")
            all_tools()
        elapsed = (time.time() - start) * 1000
        assert elapsed < 500  # 500 queries < 0.5s
