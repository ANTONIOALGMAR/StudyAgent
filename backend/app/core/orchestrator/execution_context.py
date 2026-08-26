"""Execution Context — contexto compartilhado durante a execução.

Acompanha toda a execução de uma requisição do usuário.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .evidence import EvidenceStore
from .execution_plan import ExecutionPlan


@dataclass
class ExecutionContext:
    """Contexto completo de uma execução."""

    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    session_id: str = ""
    user_message: str = ""
    intent: str = ""
    plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    evidence: EvidenceStore = field(default_factory=EvidenceStore)
    artifacts: dict[str, Any] = field(default_factory=dict)
    tool_results: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    monitor: int | None = None
    active_window: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    permissions: dict[str, bool] = field(default_factory=dict)
    timestamps: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

    def record_start(self, step_id: str) -> None:
        self.timestamps[f"{step_id}_start"] = time.time()

    def record_end(self, step_id: str) -> float:
        start_key = f"{step_id}_start"
        start = self.timestamps.get(start_key, self.started_at)
        elapsed = (time.time() - start) * 1000
        self.timestamps[f"{step_id}_end"] = time.time()
        self.timestamps[f"{step_id}_duration_ms"] = elapsed
        return elapsed

    def store_result(self, step_id: str, result: Any) -> None:
        self.tool_results[step_id] = result

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    def add_tool(self, tool_name: str) -> None:
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)

    @property
    def elapsed_ms(self) -> float:
        return (time.time() - self.started_at) * 1000

    def summary(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "user_message": self.user_message[:100],
            "intent": self.intent,
            "monitor": self.monitor,
            "tools_used": self.tools_used,
            "errors": self.errors,
            "evidence": self.evidence.summary(),
            "elapsed_ms": round(self.elapsed_ms, 1),
            "steps": len(self.plan.steps),
        }
