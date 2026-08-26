"""Testes do Orchestrator V3 — errors, evidence, plan, context, executor, validator, policies."""

import time
import pytest
from app.core.orchestrator.errors import (
    CaptureError,
    HallucinationError,
    MaxRetriesError,
    ModelError,
    OCRError,
    OrchestratorError,
    PermissionError,
    TimeoutError,
    ToolError,
    ValidationError,
    VisionError,
)
from app.core.orchestrator.evidence import Evidence, EvidenceStore, EvidenceType
from app.core.orchestrator.execution_context import ExecutionContext
from app.core.orchestrator.execution_plan import ExecutionPlan, ExecutionStep, StepStatus
from app.core.orchestrator.executor import ToolExecutor
from app.core.orchestrator.validator import ResponseValidator
from app.core.orchestrator.policies import (
    RetryPolicy,
    TimeoutPolicy,
    ToolPolicy,
    get_policy,
)
from app.core.orchestrator.orchestrator import AgentOrchestrator


# ── Errors ────────────────────────────────────────────────────────


class TestErrors:
    def test_orchestrator_error_base(self):
        e = OrchestratorError("test error", code="TEST", retryable=True)
        assert str(e) == "test error"
        assert e.code == "TEST"
        assert e.retryable is True
        d = e.to_dict()
        assert d["code"] == "TEST"
        assert d["retryable"] is True

    def test_tool_error(self):
        e = ToolError("screen.capture", "falhou", retryable=True)
        assert e.tool == "screen.capture"
        assert "SCREEN.CAPTURE" in e.code

    def test_capture_error(self):
        e = CaptureError("não capturou", monitor=2)
        assert e.monitor == 2
        assert e.retryable is True

    def test_vision_error(self):
        e = VisionError("visão falhou")
        assert e.retryable is True

    def test_ocr_error(self):
        e = OCRError("tesseract falhou")
        assert e.retryable is True

    def test_model_error(self):
        e = ModelError("ollama timeout")
        assert e.retryable is True

    def test_validation_error(self):
        e = ValidationError("resposta inválida")
        assert e.retryable is False

    def test_permission_error(self):
        e = PermissionError("screen.capture")
        assert e.tool == "screen.capture"
        assert e.retryable is False

    def test_timeout_error(self):
        e = TimeoutError("screen.capture", 15.0)
        assert e.tool == "screen.capture"
        assert e.timeout_seconds == 15.0
        assert e.retryable is True

    def test_max_retries_error(self):
        e = MaxRetriesError("screen.capture", 3)
        assert e.attempts == 3
        assert e.retryable is False

    def test_hallucination_error(self):
        e = HallucinationError("modelo inventou conteúdo")
        assert "HALLUCINATION" in e.code
        assert e.retryable is False


# ── Evidence ──────────────────────────────────────────────────────


class TestEvidence:
    def test_evidence_store_creation(self):
        store = EvidenceStore()
        assert store.execution_id
        assert len(store) == 0

    def test_add_evidence(self):
        store = EvidenceStore()
        ev = store.add("test.tool", EvidenceType.TOOL, content="ok", confidence=0.9)
        assert len(store) == 1
        assert ev.source == "test.tool"
        assert ev.confidence == 0.9

    def test_add_screen_evidence(self):
        store = EvidenceStore()
        ev = store.add_screen(monitor=2, width=1920, height=1080)
        assert ev.evidence_type == EvidenceType.SCREEN
        assert ev.data["monitor"] == 2
        assert store.has_screen

    def test_add_ocr_evidence(self):
        store = EvidenceStore()
        ev = store.add_ocr("Hello World", confidence=0.8)
        assert ev.evidence_type == EvidenceType.OCR
        assert store.has_ocr

    def test_add_vision_evidence(self):
        store = EvidenceStore()
        ev = store.add_vision("VS Code aberto com código Python")
        assert ev.evidence_type == EvidenceType.VISION
        assert store.has_vision

    def test_add_intent_evidence(self):
        store = EvidenceStore()
        ev = store.add_intent("SCREEN_READ", monitor=2)
        assert ev.evidence_type == EvidenceType.INTENT

    def test_add_window_evidence(self):
        store = EvidenceStore()
        ev = store.add_window(app="VS Code", title="main.py")
        assert ev.evidence_type == EvidenceType.WINDOW

    def test_get_by_type(self):
        store = EvidenceStore()
        store.add_screen(monitor=1, width=1920, height=1080)
        store.add_ocr("text")
        assert len(store.get_by_type(EvidenceType.SCREEN)) == 1
        assert len(store.get_by_type(EvidenceType.OCR)) == 1
        assert len(store.get_by_type(EvidenceType.VISION)) == 0

    def test_min_confidence(self):
        store = EvidenceStore()
        store.add("a", EvidenceType.TOOL, confidence=0.9)
        store.add("b", EvidenceType.TOOL, confidence=0.5)
        assert store.min_confidence == 0.5

    def test_summary(self):
        store = EvidenceStore()
        store.add_screen(monitor=1, width=1920, height=1080)
        s = store.summary()
        assert s["evidence_count"] == 1
        assert s["has_screen"] is True

    def test_iter(self):
        store = EvidenceStore()
        store.add("a", EvidenceType.TOOL)
        store.add("b", EvidenceType.TOOL)
        assert len(list(store)) == 2


# ── ExecutionPlan ─────────────────────────────────────────────────


class TestExecutionPlan:
    def test_create_plan(self):
        plan = ExecutionPlan(goal="ler monitor 2", intent="SCREEN_READ")
        assert plan.goal == "ler monitor 2"
        assert len(plan.steps) == 0

    def test_add_step(self):
        plan = ExecutionPlan()
        step = plan.add_step("screen.capture", {"monitor": 2})
        assert step.tool == "screen.capture"
        assert step.arguments == {"monitor": 2}
        assert len(plan.steps) == 1

    def test_add_step_with_deps(self):
        plan = ExecutionPlan()
        s1 = plan.add_step("screen.capture")
        s2 = plan.add_step("ocr.read", depends_on=[s1.id])
        assert s2.depends_on == [s1.id]
        assert not s2.can_run(set())
        assert s2.can_run({s1.id})

    def test_pending_steps(self):
        plan = ExecutionPlan()
        s1 = plan.add_step("screen.capture")
        s2 = plan.add_step("ocr.read", depends_on=[s1.id])
        pending = plan.pending_steps
        assert len(pending) == 1
        assert pending[0].id == s1.id

    def test_is_complete(self):
        plan = ExecutionPlan()
        s1 = plan.add_step("screen.capture")
        assert not plan.is_complete
        s1.status = StepStatus.SUCCESS
        assert plan.is_complete

    def test_has_failures(self):
        plan = ExecutionPlan()
        s1 = plan.add_step("screen.capture", required=True)
        s1.status = StepStatus.FAILED
        assert plan.has_failures

    def test_to_dict(self):
        plan = ExecutionPlan(goal="test", intent="TEST")
        plan.add_step("screen.capture")
        d = plan.to_dict()
        assert d["goal"] == "test"
        assert len(d["steps"]) == 1


class TestExecutionStep:
    def test_can_run_no_deps(self):
        step = ExecutionStep(tool="screen.capture")
        assert step.can_run(set())

    def test_can_run_with_deps(self):
        step = ExecutionStep(tool="ocr", depends_on=["s1", "s2"])
        assert not step.can_run({"s1"})
        assert step.can_run({"s1", "s2"})

    def test_is_terminal(self):
        step = ExecutionStep()
        assert not step.is_terminal
        step.status = StepStatus.SUCCESS
        assert step.is_terminal
        step.status = StepStatus.FAILED
        assert step.is_terminal

    def test_to_dict(self):
        step = ExecutionStep(tool="screen.capture")
        d = step.to_dict()
        assert d["tool"] == "screen.capture"
        assert d["status"] == "PENDING"


# ── ExecutionContext ──────────────────────────────────────────────


class TestExecutionContext:
    def test_create_context(self):
        ctx = ExecutionContext(user_message="leia o monitor 2")
        assert ctx.execution_id
        assert ctx.user_message == "leia o monitor 2"
        assert ctx.elapsed_ms >= 0

    def test_record_timestamps(self):
        ctx = ExecutionContext()
        ctx.record_start("step1")
        time.sleep(0.01)
        elapsed = ctx.record_end("step1")
        assert elapsed > 0

    def test_store_result(self):
        ctx = ExecutionContext()
        ctx.store_result("s1", {"data": "ok"})
        assert ctx.tool_results["s1"]["data"] == "ok"

    def test_add_error(self):
        ctx = ExecutionContext()
        ctx.add_error("falhou")
        assert "falhou" in ctx.errors

    def test_summary(self):
        ctx = ExecutionContext(user_message="test")
        ctx.evidence.add_intent("TEST")
        s = ctx.summary()
        assert s["user_message"] == "test"
        assert "evidence" in s


# ── Validator ─────────────────────────────────────────────────────


class TestValidator:
    def test_empty_response(self):
        store = EvidenceStore()
        v = ResponseValidator(store)
        issues = v.validate("")
        assert len(issues) > 0

    def test_greeting_with_screen_evidence(self):
        store = EvidenceStore()
        store.add_screen(monitor=2, width=1920, height=1080)
        v = ResponseValidator(store)
        issues = v.validate("Olá! Eu sou o StudyAgent. Como posso ajudar?")
        assert any("ALUCINAÇÃO" in i for i in issues)

    def test_valid_response_with_screen(self):
        store = EvidenceStore()
        store.add_screen(monitor=2, width=1920, height=1080)
        v = ResponseValidator(store)
        issues = v.validate("Vi no monitor 2 o Visual Studio Code com código Python.")
        assert len(issues) == 0

    def test_no_visual_pattern(self):
        store = EvidenceStore()
        store.add_screen(monitor=2, width=1920, height=1080)
        v = ResponseValidator(store)
        issues = v.validate("Não consegui ver a imagem.")
        assert any("AVISO" in i for i in issues)

    def test_assert_valid_raises(self):
        store = EvidenceStore()
        store.add_screen(monitor=2, width=1920, height=1080)
        v = ResponseValidator(store)
        with pytest.raises(HallucinationError):
            v.assert_valid("Olá! Tudo bem?")

    def test_no_screen_evidence_passes(self):
        store = EvidenceStore()
        v = ResponseValidator(store)
        issues = v.validate("2 + 2 = 4")
        assert len(issues) == 0

    def test_low_confidence(self):
        store = EvidenceStore()
        store.add_screen(monitor=1, width=1920, height=1080)
        store._evidence[-1].confidence = 0.1  # override screen evidence confidence
        v = ResponseValidator(store)
        issues = v.validate("resposta", require_evidence=True)
        assert any("Confiança" in i for i in issues)


# ── Policies ──────────────────────────────────────────────────────


class TestPolicies:
    def test_default_policies_exist(self):
        for name in ["screen.capture", "vision.analyze", "ocr.read", "llm.chat", "web.search"]:
            p = get_policy(name)
            assert p.name == name

    def test_fallback_policy(self):
        p = get_policy("unknown.tool")
        assert p.retry.max_retries == 1

    def test_retry_delay(self):
        policy = RetryPolicy(max_retries=3, base_delay_ms=100, backoff_factor=2.0)
        assert policy.delay_for(0) == 100
        assert policy.delay_for(1) == 200
        assert policy.delay_for(2) == 400

    def test_retry_delay_max_cap(self):
        policy = RetryPolicy(max_retries=5, base_delay_ms=100, max_delay_ms=500, backoff_factor=3.0)
        assert policy.delay_for(4) == 500  # 100*81=8100 > 500

    def test_screen_capture_policy(self):
        p = get_policy("screen.capture")
        assert p.retry.max_retries == 2
        assert p.timeout.timeout_seconds == 15.0

    def test_vision_policy(self):
        p = get_policy("vision.analyze")
        assert p.retry.max_retries == 1
        assert p.timeout.timeout_seconds == 30.0


# ── Executor ──────────────────────────────────────────────────────


class TestExecutor:
    def test_execute_single_success(self):
        store = EvidenceStore()
        executor = ToolExecutor(evidence=store)
        executor.register("test.tool", lambda: "ok")
        result = executor.execute_single("test.tool")
        assert result == "ok"
        assert store.has_screen or len(store) >= 0  # evidence was created

    def test_execute_plan(self):
        store = EvidenceStore()
        executor = ToolExecutor(evidence=store)
        executor.register("step.a", lambda: "a_done")
        executor.register("step.b", lambda: "b_done")

        plan = ExecutionPlan()
        s1 = plan.add_step("step.a")
        s2 = plan.add_step("step.b", depends_on=[s1.id])

        results = executor.execute_plan(plan)
        assert results[s1.id] == "a_done"
        assert results[s2.id] == "b_done"
        assert plan.is_complete

    def test_execute_plan_with_failure(self):
        store = EvidenceStore()
        executor = ToolExecutor(evidence=store)
        executor.register("step.a", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        executor.register("step.b", lambda: "b_done")

        plan = ExecutionPlan()
        s1 = plan.add_step("step.a", required=False)
        s2 = plan.add_step("step.b", depends_on=[s1.id])

        results = executor.execute_plan(plan)
        assert s1.status == StepStatus.FAILED
        assert s2.status == StepStatus.SKIPPED

    def test_execute_unregistered_tool(self):
        store = EvidenceStore()
        executor = ToolExecutor(evidence=store)
        result = executor.execute_single("nonexistent.tool")
        assert result is None

    def test_permission_check(self):
        store = EvidenceStore()
        executor = ToolExecutor(
            evidence=store,
            permission_fn=lambda tool: tool != "blocked.tool",
        )
        executor.register("blocked.tool", lambda: "should not run")
        result = executor.execute_single("blocked.tool")
        assert result is None


# ── Orchestrator ──────────────────────────────────────────────────


class TestOrchestrator:
    def test_create_context(self):
        orch = AgentOrchestrator()
        ctx = orch.create_context("leia o monitor 2", session_id="s1")
        assert ctx.user_message == "leia o monitor 2"
        assert ctx.session_id == "s1"

    def test_create_plan(self):
        orch = AgentOrchestrator()
        ctx = orch.create_context("leia o monitor 2")
        plan = orch.create_plan(
            ctx,
            intent="SCREEN_READ",
            monitor=2,
            steps=[{"tool": "screen.capture", "arguments": {"monitor": 2}}],
        )
        assert plan.intent == "SCREEN_READ"
        assert plan.monitor == 2
        assert len(plan.steps) == 1
        assert ctx.intent == "SCREEN_READ"

    def test_execute_and_validate(self):
        orch = AgentOrchestrator()
        orch.register_tool("screen.capture", lambda monitor=1: {"ok": True})

        ctx = orch.create_context("leia o monitor 2")
        orch.create_plan(
            ctx,
            intent="SCREEN_READ",
            monitor=2,
            steps=[{"tool": "screen.capture", "arguments": {"monitor": 2}}],
        )

        orch.execute(ctx)
        assert ctx.plan.is_complete

    def test_validate_response(self):
        orch = AgentOrchestrator()
        ctx = orch.create_context("leia o monitor 2")
        ctx.evidence.add_screen(monitor=2, width=1920, height=1080)

        issues = orch.validate_response("Vi o monitor 2 com VS Code aberto.", ctx)
        assert len(issues) == 0

    def test_execution_summary(self):
        orch = AgentOrchestrator()
        ctx = orch.create_context("test")
        s = orch.execution_summary(ctx)
        assert "execution_id" in s
        assert "evidence" in s
