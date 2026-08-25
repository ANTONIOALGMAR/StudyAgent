"""Dashboard de progresso do aluno.

Consulta SQLite e retorna estatísticas de exercícios, flashcards e planos
de estudo. Tudo read-only — sem efeitos colaterais.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..config import MEMORY_DB_PATH


def _conn():
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def exercise_stats() -> dict:
    """Stats from exercise_history: total sessions, avg percent, streak, recent."""
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0]
        row = conn.execute(
            "SELECT AVG(percent) as avg_pct, SUM(score) as total_correct, "
            "SUM(total) as total_questions FROM exercise_history"
        ).fetchone()
        avg_pct = round(row["avg_pct"] or 0, 1)
        total_correct = row["total_correct"] or 0
        total_questions = row["total_questions"] or 0

        streak = 0
        today = datetime.now().date()
        for offset in range(60):
            day = (today - timedelta(days=offset)).isoformat()
            has = conn.execute(
                "SELECT 1 FROM exercise_history WHERE date(created_at) = ? LIMIT 1",
                (day,),
            ).fetchone()
            if has:
                streak += 1
            elif offset > 0:
                break

        recent = conn.execute(
            "SELECT topic, score, total, percent, created_at FROM exercise_history "
            "ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()

    return {
        "total_sessions": total,
        "avg_percent": avg_pct,
        "total_correct": total_correct,
        "total_questions": total_questions,
        "streak_days": streak,
        "recent": [dict(r) for r in recent],
    }


def flashcard_stats() -> dict:
    """Global flashcard stats: total decks, cards, due, mastered."""
    conn = _conn()
    try:
        decks = conn.execute("SELECT COUNT(*) FROM flashcard_decks").fetchone()[0]
        total_cards = conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0]
        due = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE next_review <= ?",
            (datetime.now().isoformat(),),
        ).fetchone()[0]
        mastered = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE interval_days >= 21"
        ).fetchone()[0]
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        reviews_week = conn.execute(
            "SELECT COUNT(*) FROM flashcard_reviews WHERE reviewed_at >= ?",
            (week_ago,),
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "total_decks": decks,
        "total_cards": total_cards,
        "due_now": due,
        "mastered": mastered,
        "reviews_last_7d": reviews_week,
    }


def study_plan_stats() -> dict:
    """Stats from study_plans: total plans, completion rates."""
    conn = _conn()
    try:
        plans = conn.execute(
            "SELECT id, title, total_items, done_items, created_at FROM study_plans "
            "ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        total_plans = conn.execute("SELECT COUNT(*) FROM study_plans").fetchone()[0]
        total_items = conn.execute("SELECT COUNT(*) FROM study_items").fetchone()[0]
        done_items = conn.execute(
            "SELECT COUNT(*) FROM study_items WHERE done = 1"
        ).fetchone()[0]
    finally:
        conn.close()

    plan_list = []
    for p in plans:
        p = dict(p)
        p["percent"] = round(100 * p["done_items"] / max(p["total_items"], 1))
        plan_list.append(p)

    return {
        "total_plans": total_plans,
        "total_items": total_items,
        "done_items": done_items,
        "overall_percent": round(100 * done_items / max(total_items, 1)),
        "plans": plan_list,
    }


def dashboard() -> dict:
    """Combined dashboard for the stats panel."""
    return {
        "exercises": exercise_stats(),
        "flashcards": flashcard_stats(),
        "study_plans": study_plan_stats(),
    }


def save_exercise_result(
    exercise_id: str,
    topic: str,
    score: int,
    total: int,
    percent: int,
    level: str = "",
) -> None:
    """Persist a graded exercise to exercise_history."""
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    try:
        conn.execute(
            "INSERT INTO exercise_history "
            "(exercise_id, topic, score, total, percent, level, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (exercise_id, topic, score, total, percent, level, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
