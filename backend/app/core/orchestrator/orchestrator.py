"""Agent Orchestrator — orquestração profissional do StudyAgent.

Fluxo:
  USER REQUEST
  → INTENT ANALYSIS
  → PLANNING (ExecutionPlan)
  → EXECUTION (steps com retry/timeout)
  → EVIDENCE COLLECTION
  → RESPONSE VALIDATION
  → FINAL RESPONSE

Cada execução possui um execution_id para rastreabilidade.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .execution_context import ExecutionContext
from .execution_plan import ExecutionPlan, StepStatus
from .executor import ToolExecutor
from .validator import ResponseValidator

log = logging.getLogger("studyagent.orchestrator")


class AgentOrchestrator:
    """Orquestrador profissional do StudyAgent.

    Coordena: intenção → plano → execução → evidência → validação → resposta.
    """

    def __init__(self):
        self._tool_handlers: dict[str, Callable[..., Any]] = {}
        self._permission_fn: Callable[[str], bool] | None = None

    def register_tool(self, name: str, handler: Callable[..., Any]) -> None:
        self._tool_handlers[name] = handler

    def set_permission_fn(self, fn: Callable[[str], bool]) -> None:
        self._permission_fn = fn

    def create_context(
        self,
        user_message: str,
        session_id: str = "",
    ) -> ExecutionContext:
        """Cria contexto de execução para uma nova requisição."""
        return ExecutionContext(
            session_id=session_id,
            user_message=user_message,
        )

    def create_plan(
        self,
        ctx: ExecutionContext,
        *,
        intent: str = "",
        monitor: int | None = None,
        steps: list[dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        """Cria plano de execução baseado na intenção."""
        plan = ExecutionPlan(
            goal=ctx.user_message,
            intent=intent,
            monitor=monitor,
        )

        if steps:
            for step_def in steps:
                plan.add_step(
                    tool=step_def["tool"],
                    arguments=step_def.get("arguments", {}),
                    depends_on=step_def.get("depends_on", []),
                    required=step_def.get("required", True),
                    timeout=step_def.get("timeout", 30.0),
                )

        ctx.plan = plan
        ctx.intent = intent
        ctx.monitor = monitor
        ctx.evidence.add_intent(intent, monitor)

        return plan

    def execute(self, ctx: ExecutionContext) -> dict[str, Any]:
        """Executa o plano e coleta evidências."""
        executor = ToolExecutor(
            evidence=ctx.evidence,
            permission_fn=self._permission_fn,
        )
        for name, handler in self._tool_handlers.items():
            executor.register(name, handler)

        results = executor.execute_plan(ctx.plan)

        for step in ctx.plan.steps:
            if step.status == StepStatus.SUCCESS:
                ctx.store_result(step.id, step.result)
            elif step.status == StepStatus.FAILED:
                ctx.add_error(f"{step.tool}: {step.error}")

        return results

    def validate_response(
        self,
        response: str,
        ctx: ExecutionContext,
    ) -> list[str]:
        """Valida resposta do LLM contra evidências."""
        validator = ResponseValidator(ctx.evidence)
        return validator.validate(response)

    def assert_valid_response(
        self,
        response: str,
        ctx: ExecutionContext,
    ) -> None:
        """Levanta exceção se resposta inválida."""
        validator = ResponseValidator(ctx.evidence)
        validator.assert_valid(response)

    def execution_summary(self, ctx: ExecutionContext) -> dict:
        """Retorna resumo completo da execução."""
        return ctx.summary()
