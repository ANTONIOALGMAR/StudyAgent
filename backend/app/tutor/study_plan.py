"""Planos de estudo gerados por LLM com checklist persistente.

O LLM decompõe um tema em subtópicos estruturados. O aluno marca
itens como concluídos — o progresso é salvo em SQLite.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime

from ..agent.llm import chat
from ..db import get_connection

_GEN_PROMPT = (
    "Você é um planejador de estudo escolar brasileiro.\n"
    "Gere um plano de estudo sobre: {topic}.\n"
    "Nível: {level}. O plano deve ter entre 5 e 12 itens concretos.\n"
    "Cada item é um subtópico específico para estudar (não genérico).\n"
    "{mastery_hint}\n\n"
    'Responda ESTRITAMENTE neste JSON, sem texto fora dele:\n'
    '{{"title": "Título do plano", "items": [{{"title": "subtópico", '
    '"detail": "uma frase curta explicando o que estudar"}}]}}'
)


def _build_mastery_hint(topic: str) -> str:
    """Build a hint about the student's mastery for the topic."""
    try:
        from .error_notebook import get_errors_by_topic
        from .profile import topic_details

        details = topic_details(topic)
        errors = get_errors_by_topic(topic)

        hints = []
        if details:
            ws = details.get("weighted_score", details.get("avg_percent", 0))
            attempts = details.get("attempts", 0)
            if ws < 55:
                hints.append(f"O aluno tem dificuldade neste tema (mastery: {ws}%, {attempts} tentativas). Priorize fundamentos.")
            elif ws >= 80:
                hints.append(f"O aluno já domina bem este tema (mastery: {ws}%). Foque em avançado/revisão rápida.")
            else:
                hints.append(f"Mastery intermediário ({ws}%, {attempts} tentativas). Reforce pontos fracos.")

        if errors:
            error_topics = set(e["question"][:50] for e in errors[:3])
            hints.append(f"O aluno errou recentemente em: {'; '.join(error_topics)}. Inclua exercícios sobre esses pontos.")

        return " ".join(hints) if hints else ""
    except Exception:
        return ""


def generate_plan(
    topic: str,
    level: str = "ensino fundamental",
    memory=None,
) -> dict:
    mastery_hint = _build_mastery_hint(topic)
    prompt = _GEN_PROMPT.format(topic=topic, level=level, mastery_hint=mastery_hint)
    raw = chat([{"role": "user", "content": prompt}])
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    title = data.get("title") or topic
    items = data.get("items") or []

    if not items:
        raise ValueError("O modelo não gerou um plano válido. Tente outro tema.")

    plan_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO study_plans (id, title, topic, total_items, done_items, created_at) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (plan_id, title, topic, len(items), now),
    )
    for i, item in enumerate(items[:15]):
        conn.execute(
            "INSERT INTO study_items (plan_id, title, detail, done, sort_order) VALUES (?, ?, ?, 0, ?)",
            (plan_id, item.get("title", ""), item.get("detail", ""), i),
        )
    conn.commit()

    return {
        "plan_id": plan_id,
        "title": title,
        "topic": topic,
        "total_items": len(items),
        "items": [
            {"title": it.get("title", ""), "detail": it.get("detail", ""), "done": False}
            for it in items
        ],
    }


def list_plans() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM study_plans ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_plan(plan_id: str) -> dict | None:
    conn = get_connection()
    plan_row = conn.execute("SELECT * FROM study_plans WHERE id = ?", (plan_id,)).fetchone()
    if not plan_row:
        return None
    plan = dict(plan_row)
    items = conn.execute(
        "SELECT * FROM study_items WHERE plan_id = ? ORDER BY sort_order", (plan_id,)
    ).fetchall()
    plan["items"] = [dict(it) for it in items]
    return plan


def toggle_item(item_id: int) -> dict:
    conn = get_connection()
    item = conn.execute("SELECT * FROM study_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        raise KeyError(f"Item {item_id} não encontrado")
    item = dict(item)
    new_done = 0 if item["done"] else 1
    conn.execute("UPDATE study_items SET done = ? WHERE id = ?", (new_done, item_id))
    plan_id = item["plan_id"]
    total = conn.execute(
        "SELECT COUNT(*) FROM study_items WHERE plan_id = ?", (plan_id,)
    ).fetchone()[0]
    done = conn.execute(
        "SELECT COUNT(*) FROM study_items WHERE plan_id = ? AND done = 1", (plan_id,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE study_plans SET total_items = ?, done_items = ? WHERE id = ?",
        (total, done, plan_id),
    )
    conn.commit()
    return {"item_id": item_id, "done": bool(new_done), "plan_id": plan_id, "done_items": done, "total_items": total}
