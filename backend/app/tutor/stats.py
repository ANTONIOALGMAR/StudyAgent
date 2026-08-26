"""Dashboard de progresso do aluno.

Consulta SQLite e retorna estatísticas de exercícios, flashcards e planos
de estudo. Tudo read-only — sem efeitos colaterais.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..db import get_connection


def exercise_stats() -> dict:
    conn = get_connection()
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
            "SELECT 1 FROM exercise_history WHERE date(created_at) = ? LIMIT 1", (day,)
        ).fetchone()
        if has:
            streak += 1
        elif offset > 0:
            break

    recent = conn.execute(
        "SELECT topic, score, total, percent, created_at FROM exercise_history "
        "ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    return {
        "total_sessions": total,
        "avg_percent": avg_pct,
        "total_correct": total_correct,
        "total_questions": total_questions,
        "streak_days": streak,
        "recent": [dict(r) for r in recent],
    }


def flashcard_stats() -> dict:
    conn = get_connection()
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

    return {
        "total_decks": decks,
        "total_cards": total_cards,
        "due_now": due,
        "mastered": mastered,
        "reviews_last_7d": reviews_week,
    }


def study_plan_stats() -> dict:
    conn = get_connection()
    plans = conn.execute(
        "SELECT id, title, total_items, done_items, created_at FROM study_plans "
        "ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    total_plans = conn.execute("SELECT COUNT(*) FROM study_plans").fetchone()[0]
    total_items = conn.execute("SELECT COUNT(*) FROM study_items").fetchone()[0]
    done_items = conn.execute(
        "SELECT COUNT(*) FROM study_items WHERE done = 1"
    ).fetchone()[0]

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
    conn = get_connection()
    conn.execute(
        "INSERT INTO exercise_history "
        "(exercise_id, topic, score, total, percent, level, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (exercise_id, topic, score, total, percent, level, datetime.now().isoformat()),
    )
    conn.commit()


def mastery_by_subject() -> list[dict]:
    """Group mastery topics by subject area.

    Returns a list of subjects with their topics, sorted by average mastery.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT topic, weighted_score, avg_percent, attempts, last_practiced "
        "FROM topic_mastery ORDER BY weighted_score ASC"
    ).fetchall()

    subjects: dict[str, list[dict]] = {}
    for r in rows:
        r = dict(r)
        topic = r["topic"]
        # Simple heuristic: use the topic name as subject
        # (in future, could use LLM to categorize)
        subject = topic
        if subject not in subjects:
            subjects[subject] = []
        subjects[subject].append({
            "topic": topic,
            "weighted_score": r.get("weighted_score") or r["avg_percent"],
            "attempts": r["attempts"],
            "last_practiced": r.get("last_practiced"),
        })

    result = []
    for subject, topics in subjects.items():
        avg_score = sum(t["weighted_score"] for t in topics) / len(topics)
        result.append({
            "subject": subject,
            "avg_score": round(avg_score, 1),
            "topic_count": len(topics),
            "topics": topics,
            "status": "weak" if avg_score < 55 else "strong" if avg_score >= 80 else "neutral",
        })

    result.sort(key=lambda s: s["avg_score"])
    return result


def weekly_summary() -> dict:
    """Summary of the last 7 days of study activity."""
    conn = get_connection()
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    exercises = conn.execute(
        "SELECT COUNT(*) as count, AVG(percent) as avg_pct, "
        "SUM(score) as correct, SUM(total) as total_q "
        "FROM exercise_history WHERE created_at >= ?",
        (week_ago,),
    ).fetchone()

    flashcard_reviews = conn.execute(
        "SELECT COUNT(*) as count FROM flashcard_reviews WHERE reviewed_at >= ?",
        (week_ago,),
    ).fetchone()

    study_time = conn.execute(
        "SELECT SUM(duration_seconds) as total_sec FROM session_log "
        "WHERE started_at >= ? AND duration_seconds IS NOT NULL",
        (week_ago,),
    ).fetchone()

    topics_practiced = conn.execute(
        "SELECT COUNT(DISTINCT topic) as count FROM topic_results WHERE created_at >= ?",
        (week_ago,),
    ).fetchone()

    new_errors = conn.execute(
        "SELECT COUNT(*) as count FROM error_notebook WHERE created_at >= ?",
        (week_ago,),
    ).fetchone()

    return {
        "period": "7 dias",
        "exercises": {
            "count": exercises["count"] or 0,
            "avg_percent": round(exercises["avg_pct"] or 0, 1),
            "correct": exercises["correct"] or 0,
            "total_questions": exercises["total_q"] or 0,
        },
        "flashcard_reviews": flashcard_reviews["count"] or 0,
        "study_minutes": round((study_time["total_sec"] or 0) / 60),
        "topics_practiced": topics_practiced["count"] or 0,
        "new_errors": new_errors["count"] or 0,
    }


def error_summary() -> dict:
    """Summary of error notebook for the dashboard."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM error_notebook").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM error_notebook WHERE reviewed = 0"
    ).fetchone()[0]
    by_topic = conn.execute(
        "SELECT topic, COUNT(*) as count FROM error_notebook "
        "WHERE reviewed = 0 GROUP BY topic ORDER BY count DESC LIMIT 5"
    ).fetchall()

    return {
        "total_errors": total,
        "pending_review": pending,
        "top_error_topics": [{"topic": r["topic"], "count": r["count"]} for r in by_topic],
    }


def enhanced_dashboard() -> dict:
    """Full dashboard combining all data sources."""
    base = dashboard()
    return {
        **base,
        "mastery_by_subject": mastery_by_subject(),
        "weekly_summary": weekly_summary(),
        "error_summary": error_summary(),
    }
