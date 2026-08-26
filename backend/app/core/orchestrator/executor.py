"""Tool Executor — executa steps com retry, timeout e evidências.

Cada step é uma chamada de ferramenta que pode falhar e ser retryada.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .errors import (
    PermissionError,
)
from .evidence import EvidenceStore, EvidenceType
from .execution_plan import ExecutionPlan, ExecutionStep, StepStatus
from .policies import get_policy

log = logging.getLogger("studyagent.orchestrator")


class ToolExecutor:
    """Executa steps de um ExecutionPlan."""

    def __init__(
        self,
        evidence: EvidenceStore,
        permission_fn: Callable[[str], bool] | None = None,
    ):
        self.evidence = evidence
        self._permission_fn = permission_fn
        self._tool_handlers: dict[str, Callable[..., Any]] = {}

    def register(self, tool_name: str, handler: Callable[..., Any]) -> None:
        self._tool_handlers[tool_name] = handler

    def execute_plan(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Executa todos os steps do plano na ordem de dependências."""
        results: dict[str, Any] = {}

        max_iterations = plan.max_steps
        iteration = 0

        while not plan.is_complete and iteration < max_iterations:
            iteration += 1
            pending = plan.pending_steps

            if not pending:
                # Steps restantes têm dependências não resolvidas
                blocked = [s for s in plan.steps if s.status == StepStatus.PENDING]
                if blocked:
                    log.warning("[EXECUTOR] blocked_steps=%d", len(blocked))
                    for s in blocked:
                        s.status = StepStatus.SKIPPED
                break

            for step in pending:
                result = self._execute_step(step, plan)
                results[step.id] = result

        return results

    def _execute_step(self, step: ExecutionStep, plan: ExecutionPlan) -> Any:
        """Executa um step individual com retry."""
        policy = get_policy(step.tool)
        step.status = StepStatus.RUNNING

        # Verificar permissão
        if self._permission_fn and not self._permission_fn(step.tool):
            step.status = StepStatus.FAILED
            step.error = f"Permissão negada para {step.tool}"
            self.evidence.add(
                source=step.tool,
                evidence_type=EvidenceType.TOOL,
                content=f"Permissão negada: {step.tool}",
                confidence=0.0,
            )
            return None

        # Verificar se handler existe
        handler = self._tool_handlers.get(step.tool)
        if not handler:
            step.status = StepStatus.FAILED
            step.error = f"Handler não registrado: {step.tool}"
            self.evidence.add(
                source=step.tool,
                evidence_type=EvidenceType.TOOL,
                content=f"Handler não encontrado: {step.tool}",
                confidence=0.0,
            )
            return None

        # Executar com retry
        for attempt in range(policy.retry.max_retries + 1):
            try:
                start = time.time()
                result = handler(**step.arguments)
                elapsed_ms = (time.time() - start) * 1000

                step.status = StepStatus.SUCCESS
                step.result = result
                step.duration_ms = elapsed_ms
                step.retry_count = attempt

                log.info(
                    "[EXECUTOR] step=%s tool=%s success duration_ms=%.1f attempt=%d",
                    step.id, step.tool, elapsed_ms, attempt + 1,
                )
                return result

            except PermissionError as exc:
                step.status = StepStatus.FAILED
                step.error = str(exc)
                log.warning("[EXECUTOR] step=%s permission_denied", step.id)
                self.evidence.add(
                    source=step.tool,
                    evidence_type=EvidenceType.TOOL,
                    content=f"Permissão negada: {exc}",
                    confidence=0.0,
                )
                return None

            except Exception as exc:
                elapsed_ms = (time.time() - start) * 1000

                if attempt < policy.retry.max_retries:
                    delay = policy.retry.delay_for(attempt)
                    log.warning(
                        "[EXECUTOR] step=%s tool=%s attempt=%d failed retry_ms=%.0f error=%s",
                        step.id, step.tool, attempt + 1, delay, exc,
                    )
                    time.sleep(delay / 1000)
                else:
                    step.status = StepStatus.FAILED
                    step.error = str(exc)
                    step.retry_count = attempt
                    log.error(
                        "[EXECUTOR] step=%s tool=%s exhausted error=%s",
                        step.id, step.tool, exc,
                    )

        return None

    def execute_single(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Executa uma única ferramenta (fora do plano)."""
        step = ExecutionStep(tool=tool, arguments=arguments or {})
        return self._execute_step(step, ExecutionPlan())
