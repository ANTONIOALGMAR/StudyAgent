"""Caderno de erros: registra questões erradas para revisão futura.

Salva cada erro com contexto (tema, pergunta, resposta do aluno,
resposta correta, explicação). Permite marcar como revisado e
gerar flashcards a partir dos erros.
"""

from __future__ import annotations

from datetime import datetime

from ..db import get_connection


def log_error(
    topic: str,
    question: str,
    user_answer: str,
    correct_answer: str,
    explanation: str = "",
    exercise_id: str = "",
) -> dict:
    conn = get_connection()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO error_notebook "
        "(topic, question, user_answer, correct_answer, explanation, exercise_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (topic, question, user_answer, correct_answer, explanation, exercise_id, now),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "topic": topic}


def log_errors_from_exercise(
    exercise_id: str, topic: str, results: list[dict]
) -> int:
    """Log all wrong answers from an exercise result. Returns count logged."""
    count = 0
    for r in results:
        if not r.get("correct", True):
            log_error(
                topic=topic,
                question=r.get("q", ""),
                user_answer=r.get("user_answer", ""),
                correct_answer=r.get("expected", ""),
                explanation=r.get("explanation", ""),
                exercise_id=exercise_id,
            )
            count += 1
    return count


def get_errors_by_topic(
    topic: str, include_reviewed: bool = False
) -> list[dict]:
    conn = get_connection()
    if include_reviewed:
        rows = conn.execute(
            "SELECT * FROM error_notebook WHERE topic = ? ORDER BY created_at DESC",
            (topic,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM error_notebook WHERE topic = ? AND reviewed = 0 "
            "ORDER BY created_at DESC",
            (topic,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_errors(include_reviewed: bool = False) -> list[dict]:
    conn = get_connection()
    if include_reviewed:
        rows = conn.execute(
            "SELECT * FROM error_notebook ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM error_notebook WHERE reviewed = 0 "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def error_stats() -> dict:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM error_notebook").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM error_notebook WHERE reviewed = 0"
    ).fetchone()[0]
    by_topic = conn.execute(
        "SELECT topic, COUNT(*) as count FROM error_notebook "
        "WHERE reviewed = 0 GROUP BY topic ORDER BY count DESC LIMIT 10"
    ).fetchall()
    return {
        "total_errors": total,
        "pending_review": pending,
        "by_topic": [{"topic": r["topic"], "count": r["count"]} for r in by_topic],
    }


def mark_reviewed(error_id: int) -> bool:
    conn = get_connection()
    conn.execute(
        "UPDATE error_notebook SET reviewed = 1 WHERE id = ?", (error_id,)
    )
    conn.commit()
    return conn.total_changes > 0


def mark_topic_reviewed(topic: str) -> int:
    """Mark all errors in a topic as reviewed. Returns count."""
    conn = get_connection()
    conn.execute(
        "UPDATE error_notebook SET reviewed = 1 WHERE topic = ? AND reviewed = 0",
        (topic,),
    )
    conn.commit()
    return conn.total_changes


def errors_for_flashcards(topic: str | None = None) -> list[dict]:
    """Get unreviewed errors suitable for flashcard generation.

    Returns grouped by topic with question/answer pairs.
    """
    conn = get_connection()
    if topic:
        rows = conn.execute(
            "SELECT topic, question, correct_answer, explanation "
            "FROM error_notebook WHERE topic = ? AND reviewed = 0 "
            "ORDER BY created_at DESC LIMIT 20",
            (topic,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT topic, question, correct_answer, explanation "
            "FROM error_notebook WHERE reviewed = 0 "
            "ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]
