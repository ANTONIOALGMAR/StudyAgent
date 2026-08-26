"""Gamificação: conquistas, streaks por tema, ranking.

Verifica conquistas automaticamente com base em ações do aluno.
Mantém streaks por tema e rankings de desempenho.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from ..db import get_connection

ACHIEVEMENT_DEFS = [
    {"id": "first_exercise", "title": "Primeiro passo", "description": "Completou o primeiro exercício", "icon": "🎯", "category": "exercise", "threshold": 1},
    {"id": "exercises_10", "title": "Dedicado", "description": "Completou 10 exercícios", "icon": "📚", "category": "exercise", "threshold": 10},
    {"id": "exercises_50", "title": "Estudioso", "description": "Completou 50 exercícios", "icon": "🏆", "category": "exercise", "threshold": 50},
    {"id": "perfect_score", "title": "Perfeição", "description": "Acertou 100% em um exercício", "icon": "💎", "category": "exercise", "threshold": 100},
    {"id": "streak_3", "title": "Sequência de 3", "description": "Estudou 3 dias seguidos", "icon": "🔥", "category": "streak", "threshold": 3},
    {"id": "streak_7", "title": "Semana completa", "description": "Estudou 7 dias seguidos", "icon": "🌋", "category": "streak", "threshold": 7},
    {"id": "streak_30", "title": "Mês dedicado", "description": "Estudou 30 dias seguidos", "icon": "🌟", "category": "streak", "threshold": 30},
    {"id": "first_flashcard", "title": "Cartas do saber", "description": "Criou o primeiro baralho", "icon": "🃏", "category": "flashcard", "threshold": 1},
    {"id": "flashcards_100", "title": "Mente brilhante", "description": "Revisou 100 flashcards", "icon": "🧠", "category": "flashcard", "threshold": 100},
    {"id": "mastered_10", "title": "Domínio total", "description": "Dominou 10 cards (intervalo > 21 dias)", "icon": "👑", "category": "flashcard", "threshold": 10},
    {"id": "first_plan", "title": "Planejador", "description": "Criou o primeiro plano de estudo", "icon": "📋", "category": "study_plan", "threshold": 1},
    {"id": "plan_completed", "title": "Conquistador", "description": "Completou um plano de estudo 100%", "icon": "🎖️", "category": "study_plan", "threshold": 1},
    {"id": "plans_5", "title": "Estrategista", "description": "Completou 5 planos de estudo", "icon": "⚡", "category": "study_plan", "threshold": 5},
    {"id": "topics_5", "title": "Explorador", "description": "Estudou 5 temas diferentes", "icon": "🗺️", "category": "mastery", "threshold": 5},
    {"id": "topics_10", "title": "Polímata", "description": "Estudou 10 temas diferentes", "icon": "🎓", "category": "mastery", "threshold": 10},
    {"id": "weak_to_strong", "title": "Virada de jogo", "description": "Melhorou um tema de fraco para forte", "icon": "💪", "category": "mastery", "threshold": 1},
]


def check_achievements() -> list[dict]:
    conn = get_connection()
    already = {r["achievement_id"] for r in conn.execute(
        "SELECT achievement_id FROM achievements"
    ).fetchall()}

    newly_earned = []
    for defn in ACHIEVEMENT_DEFS:
        if defn["id"] in already:
            continue
        if _check_condition(conn, defn):
            _award(conn, defn["id"])
            newly_earned.append(defn)

    conn.commit()
    return newly_earned


def _check_condition(conn, defn: dict) -> bool:
    aid = defn["id"]
    if aid == "first_exercise":
        return conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0] >= 1
    if aid == "exercises_10":
        return conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0] >= 10
    if aid == "exercises_50":
        return conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0] >= 50
    if aid == "perfect_score":
        return conn.execute("SELECT COUNT(*) FROM exercise_history WHERE percent = 100").fetchone()[0] >= 1
    if aid == "streak_3":
        return _current_streak(conn) >= 3
    if aid == "streak_7":
        return _current_streak(conn) >= 7
    if aid == "streak_30":
        return _current_streak(conn) >= 30
    if aid == "first_flashcard":
        return conn.execute("SELECT COUNT(*) FROM flashcard_decks").fetchone()[0] >= 1
    if aid == "flashcards_100":
        return conn.execute("SELECT COUNT(*) FROM flashcard_reviews").fetchone()[0] >= 100
    if aid == "mastered_10":
        return conn.execute("SELECT COUNT(*) FROM flashcards WHERE interval_days >= 21").fetchone()[0] >= 10
    if aid == "first_plan":
        return conn.execute("SELECT COUNT(*) FROM study_plans").fetchone()[0] >= 1
    if aid == "plan_completed":
        return conn.execute(
            "SELECT COUNT(*) FROM study_plans WHERE total_items > 0 AND done_items = total_items"
        ).fetchone()[0] >= 1
    if aid == "plans_5":
        return conn.execute(
            "SELECT COUNT(*) FROM study_plans WHERE total_items > 0 AND done_items = total_items"
        ).fetchone()[0] >= 5
    if aid == "topics_5":
        return conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0] >= 5
    if aid == "topics_10":
        return conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0] >= 10
    if aid == "weak_to_strong":
        return conn.execute(
            "SELECT COUNT(*) FROM topic_mastery WHERE weighted_score >= 80 AND attempts >= 2"
        ).fetchone()[0] >= 1
    return False


def _current_streak(conn) -> int:
    streak = 0
    today = datetime.now().date()
    for offset in range(60):
        day = (today - timedelta(days=offset)).isoformat()
        has = conn.execute(
            "SELECT 1 FROM session_log WHERE date(started_at) = ? LIMIT 1", (day,)
        ).fetchone()
        if not has:
            has = conn.execute(
                "SELECT 1 FROM exercise_history WHERE date(created_at) = ? LIMIT 1", (day,)
            ).fetchone()
        if not has:
            has = conn.execute(
                "SELECT 1 FROM flashcard_reviews WHERE date(reviewed_at) = ? LIMIT 1", (day,)
            ).fetchone()
        if has:
            streak += 1
        elif offset > 0:
            break
    return streak


def _award(conn, achievement_id: str) -> None:
    conn.execute(
        "INSERT INTO achievements (id, achievement_id, earned_at) VALUES (?, ?, ?)",
        (uuid.uuid4().hex[:10], achievement_id, datetime.now().isoformat()),
    )


def list_achievements() -> list[dict]:
    conn = get_connection()
    earned = {
        r["achievement_id"]: r["earned_at"]
        for r in conn.execute("SELECT achievement_id, earned_at FROM achievements").fetchall()
    }
    result = []
    for defn in ACHIEVEMENT_DEFS:
        entry = dict(defn)
        entry["earned"] = defn["id"] in earned
        entry["earned_at"] = earned.get(defn["id"])
        result.append(entry)
    return result


def achievement_progress() -> dict:
    conn = get_connection()
    exercise_count = conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0]
    perfect_count = conn.execute("SELECT COUNT(*) FROM exercise_history WHERE percent = 100").fetchone()[0]
    streak = _current_streak(conn)
    deck_count = conn.execute("SELECT COUNT(*) FROM flashcard_decks").fetchone()[0]
    review_count = conn.execute("SELECT COUNT(*) FROM flashcard_reviews").fetchone()[0]
    mastered_count = conn.execute("SELECT COUNT(*) FROM flashcards WHERE interval_days >= 21").fetchone()[0]
    plan_count = conn.execute("SELECT COUNT(*) FROM study_plans").fetchone()[0]
    completed_plans = conn.execute(
        "SELECT COUNT(*) FROM study_plans WHERE total_items > 0 AND done_items = total_items"
    ).fetchone()[0]
    topic_count = conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0]
    strong_count = conn.execute(
        "SELECT COUNT(*) FROM topic_mastery WHERE weighted_score >= 80 AND attempts >= 2"
    ).fetchone()[0]
    earned = {r["achievement_id"] for r in conn.execute(
        "SELECT achievement_id FROM achievements"
    ).fetchall()}

    progress_map = {
        "first_exercise": {"current": exercise_count, "target": 1},
        "exercises_10": {"current": exercise_count, "target": 10},
        "exercises_50": {"current": exercise_count, "target": 50},
        "perfect_score": {"current": perfect_count, "target": 1},
        "streak_3": {"current": streak, "target": 3},
        "streak_7": {"current": streak, "target": 7},
        "streak_30": {"current": streak, "target": 30},
        "first_flashcard": {"current": deck_count, "target": 1},
        "flashcards_100": {"current": review_count, "target": 100},
        "mastered_10": {"current": mastered_count, "target": 10},
        "first_plan": {"current": plan_count, "target": 1},
        "plan_completed": {"current": completed_plans, "target": 1},
        "plans_5": {"current": completed_plans, "target": 5},
        "topics_5": {"current": topic_count, "target": 5},
        "topics_10": {"current": topic_count, "target": 10},
        "weak_to_strong": {"current": strong_count, "target": 1},
    }

    result = []
    for defn in ACHIEVEMENT_DEFS:
        if defn["id"] in earned:
            continue
        p = progress_map.get(defn["id"], {"current": 0, "target": defn["threshold"]})
        result.append({
            "id": defn["id"],
            "title": defn["title"],
            "icon": defn["icon"],
            "current": p["current"],
            "target": p["target"],
            "percent": min(100, round(100 * p["current"] / max(p["target"], 1))),
        })
    return {"locked": result, "total": len(ACHIEVEMENT_DEFS), "earned": len(earned)}


def topic_streaks() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT topic, COUNT(DISTINCT date(created_at)) as days_practiced, "
        "MAX(created_at) as last_practiced FROM exercise_history "
        "GROUP BY topic ORDER BY days_practiced DESC"
    ).fetchall()

    result = []
    for r in rows:
        r = dict(r)
        topic_streak = 0
        today = datetime.now().date()
        for offset in range(30):
            day = (today - timedelta(days=offset)).isoformat()
            has = conn.execute(
                "SELECT 1 FROM exercise_history WHERE topic = ? AND date(created_at) = ? LIMIT 1",
                (r["topic"], day),
            ).fetchone()
            if has:
                topic_streak += 1
            elif offset > 0:
                break
        result.append({
            "topic": r["topic"],
            "days_practiced": r["days_practiced"],
            "current_streak": topic_streak,
            "last_practiced": r["last_practiced"],
        })
    return result
