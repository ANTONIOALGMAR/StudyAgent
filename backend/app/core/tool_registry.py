"""Tool Registry V2 — registro central de ferramentas do agente.

Cada ferramenta declara: nome, schema Ollama, permissão exigida e handler.
O loop do agente passa a ser genérico: descobre ferramentas, pede permissão
e executa — sem cadeias de if/elif por ferramenta.

V2: versionamento, histórico de execução, descoberta de ferramentas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolExecutionStats:
    """Estatísticas de execução de uma ferramenta."""

    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration_ms: float = 0.0
    success_duration_ms: float = 0.0
    last_called_at: float = 0.0
    last_error: str | None = None

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.success_count / self.total_calls

    @property
    def avg_duration_ms(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.success_duration_ms / self.success_count

    def record_success(self, duration_ms: float) -> None:
        self.total_calls += 1
        self.success_count += 1
        self.total_duration_ms += duration_ms
        self.success_duration_ms += duration_ms
        self.last_called_at = time.time()

    def record_failure(self, error: str, duration_ms: float) -> None:
        self.total_calls += 1
        self.failure_count += 1
        self.total_duration_ms += duration_ms
        self.last_called_at = time.time()
        self.last_error = error

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 3),
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "last_error": self.last_error,
        }


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], str]
    permission: str | None = None
    required: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    stats: ToolExecutionStats = field(default_factory=ToolExecutionStats)

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "permission": self.permission,
            "required": self.required,
            "stats": self.stats.to_dict(),
        }


_REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    parameters: dict,
    permission: str | None = None,
    required: list[str] | None = None,
    version: str = "1.0.0",
    tags: list[str] | None = None,
) -> Callable:
    """Decorador que registra uma ferramenta no registry global."""

    def decorate(fn: Callable[[dict], str]) -> Callable[[dict], str]:
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
            permission=permission,
            required=required or [],
            version=version,
            tags=tags or [],
        )
        return fn

    return decorate


def get(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def all_schemas() -> list[dict]:
    return [t.schema() for t in _REGISTRY.values()]


def names() -> list[str]:
    return sorted(_REGISTRY)


def all_tools() -> list[Tool]:
    return list(_REGISTRY.values())


def by_tag(tag: str) -> list[Tool]:
    """Retorna ferramentas com uma tag específica."""
    return [t for t in _REGISTRY.values() if tag in t.tags]


def by_permission(permission: str) -> list[Tool]:
    """Retorna ferramentas que exigem uma permissão."""
    return [t for t in _REGISTRY.values() if t.permission == permission]


def discover(query: str = "", tag: str = "", permission: str = "") -> list[Tool]:
    """Descobre ferramentas por query (nome/descrição), tag ou permissão."""
    results = list(_REGISTRY.values())
    if query:
        q = query.lower()
        results = [
            t for t in results
            if q in t.name.lower() or q in t.description.lower()
        ]
    if tag:
        results = [t for t in results if tag in t.tags]
    if permission:
        results = [t for t in results if t.permission == permission]
    return results


def registry_summary() -> dict:
    """Resumo do registry para diagnóstico."""
    tools = list(_REGISTRY.values())
    return {
        "total": len(tools),
        "names": sorted(_REGISTRY.keys()),
        "by_tag": {},
        "by_permission": {},
        "stats": {
            name: t.stats.to_dict()
            for name, t in _REGISTRY.items()
            if t.stats.total_calls > 0
        },
    }


def reset_registry() -> None:
    """Útil em testes."""
    _REGISTRY.clear()
