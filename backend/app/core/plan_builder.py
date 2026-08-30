"""Plan Builder — transforma um pedido em um plano de execução multi-step.

Puro (sem I/O), acoplado ao Tool Registry para validar os nomes das
ferramentas e os argumentos. É a ponte entre o usuário e o
AgentOrchestrator: uma única pergunta pode gerar VÁRIAS ações encadeadas
(dependências), executadas em ordem pelo ToolExecutor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .tool_registry import all_tools


JSON_OPEN_RE = re.compile(r"\{", re.IGNORECASE)


@dataclass
class PlanStep:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    required: bool = True

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "depends_on": self.depends_on,
            "required": self.required,
        }


@dataclass
class BuildResult:
    """Resultado da construção do plano."""

    steps: list[PlanStep] = field(default_factory=list)
    raw: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.steps) > 0


PLAN_PROMPT = """Você é o orquestrador de tarefas de um assistente. O usuário fez um
pedido que pode exigir UMA OU MAIS ações automáticas encadeadas.

Responda APENAS com um JSON válido, sem texto, sem markdown, no formato:
{
  "steps": [
    {
      "tool": "nome_da_ferramenta",
      "arguments": { "parametro": "valor" },
      "depends_on": ["id_de_outro_passo"],
      "required": true
    }
  ]
}

Ferramentas disponíveis (nome -> o que faz):
{tools}

Regras:
- Liste TODAS as ações necessárias para atender o pedido, na ordem de
  execução. Ex.: buscar na web e depois abrir uma página.
- "depends_on" usa o índice do passo (0-based) do qual este depende
  (apenas passos anteriores). Deixe vazio [] se não depender de nada.
- "arguments" devem ter TODOS os parâmetros obrigatórios da ferramenta.
- Se o pedido pede ação de sistema/sistema, use a ferramenta adequada
  quando existir.
- Se nenhuma ferramenta é necessária, responda {{"steps": []}}.

Pedido do usuário: {message}
"""


def available_tools_prompt() -> str:
    lines = []
    for t in all_tools():
        req = ", ".join(t.required)
        desc = " ".join(t.description.split())
        lines.append(f"- {t.name} (obrigatórios: {req or 'nenhum'}): {desc[:240]}")
    if not lines:
        lines.append("- (nenhuma ferramenta registrada)")
    return "\n".join(lines)


def extract_json(raw: str) -> dict | None:
    """Extrai o primeiro objeto JSON completo de uma string (tolera lixo)."""
    if not raw:
        return None
    # Procura o primeiro '{' e tenta balancear chaves/colchetes.
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def build_plan(
    message: str,
    *,
    raw: str = "",
    llm_fn=None,
    max_steps: int = 6,
) -> BuildResult:
    """Constrói o plano de execução a partir do pedido.

    - Se `raw` for fornecido, usa-o (modo teste/injetável).
    - Caso contrário chama `llm_fn(prompt)` para obter o JSON do plano.

    Valida nomes de ferramentas e parâmetros obrigatórios contra o
    Tool Registry. Passos inválidos são descartados com aviso.
    """
    tools = {t.name: t for t in all_tools()}

    if not raw:
        if not llm_fn:
            return BuildResult(error="Nenhuma fonte de plano fornecida")
        prompt = PLAN_PROMPT.replace("{tools}", available_tools_prompt()).replace(
            "{message}", message
        )
        try:
            raw = llm_fn(prompt) or ""
        except Exception as exc:  # noqa: BLE001
            return BuildResult(raw="", error=f"Falha ao gerar plano: {exc}")

    parsed = extract_json(raw)
    if parsed is None:
        return BuildResult(raw=raw, error="Plano não é JSON válido")

    steps_raw = parsed.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        return BuildResult(raw=raw, steps=[], error=None)

    steps: list[PlanStep] = []
    seen_indices: set[int] = set()

    for idx, item in enumerate(steps_raw[:max_steps]):
        if not isinstance(item, dict):
            continue
        name = item.get("tool")
        if not name or name not in tools:
            continue
        tool = tools[name]

        arguments = item.get("arguments") or {}
        if not isinstance(arguments, dict):
            continue

        # Validar obrigatórios
        missing = [r for r in tool.required if r not in arguments or arguments[r] in (None, "")]
        if missing:
            continue

        # Dependências: só índices válidos já vistos
        depends = []
        for dep in item.get("depends_on") or []:
            if isinstance(dep, int) and dep in seen_indices:
                depends.append(str(dep))

        step = PlanStep(
            tool=name,
            arguments=arguments,
            depends_on=depends,
            required=bool(item.get("required", True)),
        )
        steps.append(step)
        seen_indices.add(idx)

    return BuildResult(steps=steps, raw=raw, error=None)
