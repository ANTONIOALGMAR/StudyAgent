"""Health — health checks do StudyAgent.

Verifica: Ollama, Tesseract, ScreenCapture, SQLite, memória.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

from ..core.tool_registry import registry_summary


@dataclass
class ComponentHealth:
    name: str
    status: str = "ok"       # ok | degraded | error
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    status: str = "ok"       # ok | degraded | error
    components: list[ComponentHealth] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "components": [
                {"name": c.name, "status": c.status, "message": c.message, "latency_ms": round(c.latency_ms, 1)}
                for c in self.components
            ],
        }


def check_ollama() -> ComponentHealth:
    t0 = time.time()
    try:
        from ..core.model_manager import _run_ollama_cmd
        from ..core.model_manager import resolve as _resolve
        model = _resolve("llm")
        result = _run_ollama_cmd(["list"])
        if model not in result:
            return ComponentHealth(
                name="ollama",
                status="degraded",
                message=f"Modelo {model} não encontrado",
                latency_ms=(time.time() - t0) * 1000,
            )
        return ComponentHealth(name="ollama", latency_ms=(time.time() - t0) * 1000)
    except Exception as exc:
        return ComponentHealth(name="ollama", status="error", message=str(exc), latency_ms=(time.time() - t0) * 1000)


def check_tesseract() -> ComponentHealth:
    t0 = time.time()
    try:
        import subprocess
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=5, check=True)
        return ComponentHealth(name="tesseract", latency_ms=(time.time() - t0) * 1000)
    except Exception as exc:
        return ComponentHealth(name="tesseract", status="error", message=str(exc), latency_ms=(time.time() - t0) * 1000)


def check_database() -> ComponentHealth:
    t0 = time.time()
    try:
        from ..config import MEMORY_DB_PATH
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        conn.execute("SELECT 1")
        conn.close()
        return ComponentHealth(name="database", latency_ms=(time.time() - t0) * 1000)
    except Exception as exc:
        return ComponentHealth(name="database", status="error", message=str(exc), latency_ms=(time.time() - t0) * 1000)


def check_screen_capture() -> ComponentHealth:
    t0 = time.time()
    try:
        from ..vision.screen import ScreenManager
        sm = ScreenManager()
        if not sm.available:
            return ComponentHealth(
                name="screen_capture",
                status="degraded",
                message="Captura de tela não disponível (missing deps?)",
                latency_ms=(time.time() - t0) * 1000,
            )
        return ComponentHealth(name="screen_capture", latency_ms=(time.time() - t0) * 1000)
    except Exception as exc:
        return ComponentHealth(name="screen_capture", status="error", message=str(exc), latency_ms=(time.time() - t0) * 1000)


def check_tool_registry() -> ComponentHealth:
    t0 = time.time()
    try:
        summary = registry_summary()
        return ComponentHealth(
            name="tool_registry",
            message=f"{summary['total']} tools registered",
            latency_ms=(time.time() - t0) * 1000,
        )
    except Exception as exc:
        return ComponentHealth(name="tool_registry", status="error", message=str(exc), latency_ms=(time.time() - t0) * 1000)


def full_health_check() -> HealthReport:
    report = HealthReport()
    checks = [check_ollama, check_tesseract, check_database, check_screen_capture, check_tool_registry]
    for check_fn in checks:
        component = check_fn()
        report.components.append(component)
    if any(c.status == "error" for c in report.components):
        report.status = "error"
    elif any(c.status == "degraded" for c in report.components):
        report.status = "degraded"
    return report
