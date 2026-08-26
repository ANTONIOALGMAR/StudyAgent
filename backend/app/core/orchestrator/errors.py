"""Hierarquia de erros do Orchestrator.

Cada ferramenta e componente retorna erros estruturados
que permitem ao Orchestrator tomar decisões de retry/fallback.
"""

from __future__ import annotations


class OrchestratorError(Exception):
    """Base para todos os erros do orchestrator."""

    def __init__(self, message: str, *, code: str = "UNKNOWN", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
        }


class ToolError(OrchestratorError):
    """Erro genérico de ferramenta."""

    def __init__(self, tool: str, message: str, *, retryable: bool = False):
        super().__init__(message, code=f"TOOL_{tool.upper()}_ERROR", retryable=retryable)
        self.tool = tool


class CaptureError(ToolError):
    """Falha na captura de tela."""

    def __init__(self, message: str, *, monitor: int | None = None, retryable: bool = True):
        super().__init__("screen.capture", message, retryable=retryable)
        self.monitor = monitor


class VisionError(ToolError):
    """Falha na análise visual (modelo de visão)."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__("vision.analyze", message, retryable=retryable)


class OCRError(ToolError):
    """Falha no OCR."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__("ocr.read", message, retryable=retryable)


class ModelError(ToolError):
    """Erro na chamada ao LLM."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__("llm.chat", message, retryable=retryable)


class ValidationError(OrchestratorError):
    """Validação de evidência ou resposta falhou."""

    def __init__(self, message: str, *, code: str = "VALIDATION_FAILED"):
        super().__init__(message, code=code, retryable=False)


class PermissionError(OrchestratorError):
    """Permissão negada."""

    def __init__(self, tool: str):
        super().__init__(
            f"Permissão negada para {tool}",
            code="PERMISSION_DENIED",
            retryable=False,
        )
        self.tool = tool


class TimeoutError(OrchestratorError):
    """Timeout de ferramenta."""

    def __init__(self, tool: str, timeout_seconds: float):
        super().__init__(
            f"Timeout de {timeout_seconds}s em {tool}",
            code="TOOL_TIMEOUT",
            retryable=True,
        )
        self.tool = tool
        self.timeout_seconds = timeout_seconds


class MaxRetriesError(OrchestratorError):
    """Limite de retries atingido."""

    def __init__(self, tool: str, attempts: int):
        super().__init__(
            f"Limite de retries atingido para {tool} após {attempts} tentativas",
            code="MAX_RETRIES",
            retryable=False,
        )
        self.tool = tool
        self.attempts = attempts


class HallucinationError(ValidationError):
    """O modelo inventou conteúdo não suportado por evidências."""

    def __init__(self, detail: str = ""):
        super().__init__(
            f"Alucinação detectada: {detail}" if detail else "Resposta contém informações não suportadas por evidências",
            code="HALLUCINATION",
        )
