"""Circuit Breaker — proteção contra falhas em cascata.

Para ferramentas que falham repetidamente, o circuit breaker abre
e rejeita chamadas futuras por um período configurável.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("studyagent.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"       # Normal — chamadas passam
    OPEN = "open"           # Falhou — chamadas rejeitadas
    HALF_OPEN = "half_open" # Testando — 1 chamada permitida


@dataclass
class CircuitBreaker:
    """Circuit breaker para uma ferramenta ou conjunto de ferramentas.

    Params:
        failure_threshold: N falhas consecutivas para abrir.
        recovery_timeout: Segundos para transição OPEN → HALF_OPEN.
        success_threshold: N sucessos em HALF_OPEN para fechar.
    """

    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    success_threshold: int = 1
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_at: float = field(default=0.0, init=False)
    last_state_change: float = field(default_factory=time.time, init=False)

    def allow(self) -> bool:
        """Verifica se a chamada deve ser permitida."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_at
            if elapsed >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
                return True
            return False

        # HALF_OPEN: permite 1 chamada de teste
        return True

    def record_success(self) -> None:
        """Registra sucesso na chamada."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Registra falha na chamada."""
        self.last_failure_at = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self.state
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
        log.info("[CIRCUIT] state=%s → %s", old.value, new_state.value)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
