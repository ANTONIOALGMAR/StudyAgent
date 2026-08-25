"""Planos de estudo gerados por LLM com checklist persistente.

O LLM decompõe um tema em subtópicos estruturados. O aluno marca
itens como concluídos — o progresso é salvo em SQLite.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime

from ..agent.llm import chat
from ..config import MEMORY_DB_PATH

_GEN_PROMPT = (
    "Você é um planejador de estudo escolar brasileiro.\n"
    "Gere um plano de estudo sobre: {topic}.\n"
    "Nível: {level}. O plano deve ter entre 5 e 12 itens concretos.\n"
    "Cada item é um subtópico específico para estudar (não genérico).\n\n"
    'Responda ESTRITAMENTE neste JSON, sem texto fora dele:\n'
    '{{"title": "Título do plano", "items": [{{"title": "subtópico", '
    '"detail": "uma frase curta explicando o que estudar"}}]}}'
)


def generate_plan(
    topic: str,
    level: str = "ensino fundamental",
    memory=None,
) -> dict:
    """Generate a study plan via LLM, persist to SQLite."""
    prompt = _GEN_PROMPT.format(topic=topic, level=level)
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

    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    try:
        conn.execute(
            "INSERT INTO study_plans (id, title, topic, total_items, done_items, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (plan_id, title, topic, len(items), now),
        )
        for i, item in enumerate(items[:15]):
            conn.execute(
                "INSERT INTO study_items (plan_id, title, detail, done, sort_order) "
                "VALUES (?, ?, ?, 0, ?)",
                (plan_id, item.get("title", ""), item.get("detail", ""), i),
            )
        conn.commit()
    finally:
        conn.close()

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
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM study_plans ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_plan(plan_id: str) -> dict | None:
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        plan_row = conn.execute(
            "SELECT * FROM study_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan_row:
            return None
        plan = dict(plan_row)
        items = conn.execute(
            "SELECT * FROM study_items WHERE plan_id = ? ORDER BY sort_order",
            (plan_id,),
        ).fetchall()
        plan["items"] = [dict(it) for it in items]
    finally:
        conn.close()
    return plan


def toggle_item(item_id: int) -> dict:
    """Toggle an item's done status and update plan counters."""
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        item = conn.execute(
            "SELECT * FROM study_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not item:
            raise KeyError(f"Item {item_id} não encontrado")
        item = dict(item)
        new_done = 0 if item["done"] else 1
        conn.execute(
            "UPDATE study_items SET done = ? WHERE id = ?", (new_done, item_id)
        )
        plan_id = item["plan_id"]
        total = conn.execute(
            "SELECT COUNT(*) FROM study_items WHERE plan_id = ?", (plan_id,)
        ).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM study_items WHERE plan_id = ? AND done = 1",
            (plan_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE study_plans SET total_items = ?, done_items = ? WHERE id = ?",
            (total, done, plan_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"item_id": item_id, "done": bool(new_done), "plan_id": plan_id, "done_items": done, "total_items": total}
