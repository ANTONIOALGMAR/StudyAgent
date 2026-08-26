"""Políticas de retry, timeout e fallback.

Cada ferramenta possui sua própria política.
O Executor usa essas políticas para controlar a execução.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("studyagent.orchestrator")


@dataclass
class RetryPolicy:
    """Política de retry para uma ferramenta."""

    max_retries: int = 2
    base_delay_ms: float = 100.0
    max_delay_ms: float = 2000.0
    backoff_factor: float = 2.0

    def delay_for(self, attempt: int) -> float:
        """Calcula delay para a tentativa N (0-indexed)."""
        delay = self.base_delay_ms * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay_ms)


@dataclass
class TimeoutPolicy:
    """Política de timeout para uma ferramenta."""

    timeout_seconds: float = 30.0
    hard_timeout_seconds: float = 60.0


@dataclass
class FallbackPolicy:
    """Política de fallback: o fazer quando a ferramenta principal falha."""

    fallback_fn: Callable[..., Any] | None = None
    fallback_message: str = ""


@dataclass
class ToolPolicy:
    """Política completa para uma ferramenta."""

    name: str
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    fallback: FallbackPolicy = field(default_factory=FallbackPolicy)
    requires_confirmation: bool = False
    dangerous: bool = False
    timeout_seconds: float = 30.0


# ── Políticas padrão por ferramenta ─────────────────────────────────

DEFAULT_POLICIES: dict[str, ToolPolicy] = {
    "screen.capture": ToolPolicy(
        name="screen.capture",
        retry=RetryPolicy(max_retries=2, base_delay_ms=200),
        timeout=TimeoutPolicy(timeout_seconds=15.0, hard_timeout_seconds=30.0),
        timeout_seconds=15.0,
    ),
    "vision.analyze": ToolPolicy(
        name="vision.analyze",
        retry=RetryPolicy(max_retries=1, base_delay_ms=500),
        timeout=TimeoutPolicy(timeout_seconds=30.0, hard_timeout_seconds=60.0),
        timeout_seconds=30.0,
    ),
    "ocr.read": ToolPolicy(
        name="ocr.read",
        retry=RetryPolicy(max_retries=2, base_delay_ms=100),
        timeout=TimeoutPolicy(timeout_seconds=10.0, hard_timeout_seconds=20.0),
        timeout_seconds=10.0,
    ),
    "llm.chat": ToolPolicy(
        name="llm.chat",
        retry=RetryPolicy(max_retries=2, base_delay_ms=1000),
        timeout=TimeoutPolicy(timeout_seconds=60.0, hard_timeout_seconds=120.0),
        timeout_seconds=60.0,
    ),
    "web.search": ToolPolicy(
        name="web.search",
        retry=RetryPolicy(max_retries=2, base_delay_ms=500),
        timeout=TimeoutPolicy(timeout_seconds=15.0, hard_timeout_seconds=30.0),
        timeout_seconds=15.0,
    ),
    "document.extract": ToolPolicy(
        name="document.extract",
        retry=RetryPolicy(max_retries=1),
        timeout=TimeoutPolicy(timeout_seconds=20.0, hard_timeout_seconds=40.0),
        timeout_seconds=20.0,
    ),
    "rag.search": ToolPolicy(
        name="rag.search",
        retry=RetryPolicy(max_retries=1),
        timeout=TimeoutPolicy(timeout_seconds=10.0, hard_timeout_seconds=20.0),
        timeout_seconds=10.0,
    ),
    "camera.capture": ToolPolicy(
        name="camera.capture",
        retry=RetryPolicy(max_retries=1),
        timeout=TimeoutPolicy(timeout_seconds=10.0, hard_timeout_seconds=20.0),
        timeout_seconds=10.0,
    ),
}


def get_policy(tool_name: str) -> ToolPolicy:
    """Retorna a política para uma ferramenta, ou política padrão."""
    return DEFAULT_POLICIES.get(
        tool_name,
        ToolPolicy(
            name=tool_name,
            retry=RetryPolicy(max_retries=1),
            timeout=TimeoutPolicy(timeout_seconds=30.0),
            timeout_seconds=30.0,
        ),
    )


def execute_with_retry(
    fn: Callable[..., Any],
    args: tuple = (),
    kwargs: dict | None = None,
    policy: ToolPolicy | None = None,
) -> Any:
    """Executa fn com retry e timeout conforme política."""
    kwargs = kwargs or {}
    policy = policy or ToolPolicy(name="unknown")
    last_error = None

    for attempt in range(policy.retry.max_retries + 1):
        try:
            log.info(
                "[POLICY] tool=%s attempt=%d/%d",
                policy.name, attempt + 1, policy.retry.max_retries + 1,
            )
            start = time.time()
            result = fn(*args, **kwargs)
            elapsed_ms = (time.time() - start) * 1000

            log.info("[POLICY] tool=%s success duration_ms=%.1f", policy.name, elapsed_ms)
            return result

        except Exception as exc:
            last_error = exc
            elapsed_ms = (time.time() - start) * 1000

            if attempt < policy.retry.max_retries:
                delay = policy.retry.delay_for(attempt)
                log.warning(
                    "[POLICY] tool=%s attempt=%d failed duration_ms=%.1f retry_ms=%.0f error=%s",
                    policy.name, attempt + 1, elapsed_ms, delay, exc,
                )
                time.sleep(delay / 1000)
            else:
                log.error(
                    "[POLICY] tool=%s exhausted attempts=%d error=%s",
                    policy.name, attempt + 1, exc,
                )

    raise last_error  # type: ignore[misc]
