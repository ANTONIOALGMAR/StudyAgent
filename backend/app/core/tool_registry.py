"""Tool Registry V2 — registro central de ferramentas do agente.

Cada ferramenta declara: nome, schema Ollama, permissão exigida e handler.
O loop do agente passa a ser genérico: descobre ferramentas, pede permissão
e executa — sem cadeias de if/elif por ferramenta.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], str]
    permission: str | None = None
    required: list[str] = field(default_factory=list)

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


_REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    parameters: dict,
    permission: str | None = None,
    required: list[str] | None = None,
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
        )
        return fn

    return decorate


def get(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def all_schemas() -> list[dict]:
    return [t.schema() for t in _REGISTRY.values()]


def names() -> list[str]:
    return sorted(_REGISTRY)


def reset_registry() -> None:
    """Útil em testes."""
    _REGISTRY.clear()
