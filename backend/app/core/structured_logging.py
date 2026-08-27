"""Structured Logging — request context propagation e campos estruturados.

Cada request recebe um request_id único que propaga por todos os módulos.
Logging padronizado com campos: request_id, session_id, user, duration_ms, etc.
"""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ── Context vars (propagam por request) ───────────────────────────

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")


def get_request_id() -> str:
    return request_id_var.get("")


def get_session_id() -> str:
    return session_id_var.get("")


def set_request_id(rid: str) -> None:
    request_id_var.set(rid)


def set_session_id(sid: str) -> None:
    session_id_var.set(sid)


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    set_request_id(rid)
    return rid


# ── Structured Logger ────────────────────────────────────────────


class StructuredLogger:
    """Logger que anexa context automaticamente."""

    def __init__(self, name: str):
        self._log = logging.getLogger(name)

    def _ctx(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx: dict[str, Any] = {"rid": get_request_id() or "-"}
        sid = get_session_id()
        if sid:
            ctx["sid"] = sid
        if extra:
            ctx.update(extra)
        return ctx

    def info(self, msg: str, **kwargs: Any) -> None:
        ctx = self._ctx(kwargs.pop("ctx", None))
        self._log.info(msg, extra=ctx, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        ctx = self._ctx(kwargs.pop("ctx", None))
        self._log.warning(msg, extra=ctx, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        ctx = self._ctx(kwargs.pop("ctx", None))
        self._log.error(msg, extra=ctx, **kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        ctx = self._ctx(kwargs.pop("ctx", None))
        self._log.debug(msg, extra=ctx, **kwargs)


# ── Timing Context Manager ───────────────────────────────────────


@dataclass
class TimingResult:
    name: str
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Timing:
    """Context manager que mede duração e loga resultado."""

    def __init__(self, name: str, log: StructuredLogger | None = None):
        self.name = name
        self.log = log or StructuredLogger("studyagent.timing")
        self._start = 0.0
        self.result: TimingResult | None = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self._start) * 1000
        success = exc_type is None
        error = ""
        if exc_val:
            error = f"{type(exc_val).__name__}: {exc_val}"
        self.result = TimingResult(
            name=self.name,
            duration_ms=elapsed_ms,
            success=success,
            error=error,
        )
        level = "info" if success else "warning"
        getattr(self.log, level)(
            f"[TIMING] {self.name} duration_ms={elapsed_ms:.1f} success={success}"
            + (f" error={error}" if error else "")
        )
        return False  # don't suppress exceptions


# ── Request ID Middleware ─────────────────────────────────────────


def setup_structured_logging():
    """Configura formato de logging estruturado."""

    class StructuredFormatter(logging.Formatter):
        def format(self, record):
            rid = getattr(record, "request_id", "") or getattr(record, "rid", "") or "-"
            sid = getattr(record, "session_id", "") or getattr(record, "sid", "") or "-"
            ts = self.formatTime(record, "%H:%M:%S")
            level = record.levelname[0]
            msg = record.getMessage()
            name = record.name.replace("studyagent.", "")
            return f"{ts} {level} [{name}] rid={rid} sid={sid} {msg}"

    root = logging.getLogger("studyagent")
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    return root
