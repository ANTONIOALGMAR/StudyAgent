"""Execution Plan — modelo estruturado de plano de execução.

O Planner gera um ExecutionPlan que o Executor segue.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


@dataclass
class ExecutionStep:
    """Um passo individual no plano de execução."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    tool: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    required: bool = True
    status: StepStatus = StepStatus.PENDING
    retry_count: int = 0
    timeout: float = 30.0
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0

    def can_run(self, completed_steps: set[str]) -> bool:
        """Verifica se todas as dependências foram concluídas."""
        return all(dep in completed_steps for dep in self.depends_on)

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            StepStatus.SUCCESS,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
            StepStatus.CANCELLED,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tool": self.tool,
            "arguments": self.arguments,
            "depends_on": self.depends_on,
            "required": self.required,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class ExecutionPlan:
    """Plano completo de execução."""

    goal: str = ""
    intent: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    max_steps: int = 10
    timeout: float = 120.0
    requires_confirmation: bool = False
    monitor: int | None = None

    def add_step(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        depends_on: list[str] | None = None,
        required: bool = True,
        timeout: float = 30.0,
    ) -> ExecutionStep:
        step = ExecutionStep(
            tool=tool,
            arguments=arguments or {},
            depends_on=depends_on or [],
            required=required,
            timeout=timeout,
        )
        self.steps.append(step)
        return step

    def get_step(self, step_id: str) -> ExecutionStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    @property
    def completed_steps(self) -> set[str]:
        return {s.id for s in self.steps if s.is_terminal and s.status != StepStatus.FAILED}

    @property
    def pending_steps(self) -> list[ExecutionStep]:
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING and s.can_run(self.completed_steps)
        ]

    @property
    def is_complete(self) -> bool:
        return all(s.is_terminal for s in self.steps)

    @property
    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED and s.required for s in self.steps)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "intent": self.intent,
            "monitor": self.monitor,
            "steps": [s.to_dict() for s in self.steps],
            "is_complete": self.is_complete,
            "has_failures": self.has_failures,
        }
