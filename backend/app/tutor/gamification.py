"""Gamificação: conquistas, streaks por tema, ranking, XP e níveis.

Verifica conquistas automaticamente com base em ações do aluno.
Sistema de XP com 5 níveis progressivos e leaderboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from ..db import get_connection

LEVEL_THRESHOLDS = [
    ("Iniciante", 0),
    ("Estudante", 100),
    ("Graduado", 300),
    ("Especialista", 600),
    ("Mestre", 1000),
]

LEVEL_ICONS = {
    "Iniciante": "🌱",
    "Estudante": "📖",
    "Graduado": "🎓",
    "Especialista": "⚡",
    "Mestre": "👑",
}

ACHIEVEMENT_DEFS = [
    {"id": "first_exercise", "title": "Primeiro passo", "description": "Completou o primeiro exercício", "icon": "🎯", "category": "exercise", "threshold": 1},
    {"id": "exercises_10", "title": "Dedicado", "description": "Completou 10 exercícios", "icon": "📚", "category": "exercise", "threshold": 10},
    {"id": "exercises_50", "title": "Estudioso", "description": "Completou 50 exercícios", "icon": "🏆", "category": "exercise", "threshold": 50},
    {"id": "exercises_100", "title": "Centenário", "description": "Completou 100 exercícios", "icon": "💯", "category": "exercise", "threshold": 100},
    {"id": "perfect_score", "title": "Perfeição", "description": "Acertou 100% em um exercício", "icon": "💎", "category": "exercise", "threshold": 100},
    {"id": "streak_3", "title": "Sequência de 3", "description": "Estudou 3 dias seguidos", "icon": "🔥", "category": "streak", "threshold": 3},
    {"id": "streak_7", "title": "Semana completa", "description": "Estudou 7 dias seguidos", "icon": "🌋", "category": "streak", "threshold": 7},
    {"id": "streak_14", "title": "Duas semanas", "description": "Estudou 14 dias seguidos", "icon": "💪", "category": "streak", "threshold": 14},
    {"id": "streak_30", "title": "Mês dedicado", "description": "Estudou 30 dias seguidos", "icon": "🌟", "category": "streak", "threshold": 30},
    {"id": "first_flashcard", "title": "Cartas do saber", "description": "Criou o primeiro baralho", "icon": "🃏", "category": "flashcard", "threshold": 1},
    {"id": "flashcards_100", "title": "Mente brilhante", "description": "Revisou 100 flashcards", "icon": "🧠", "category": "flashcard", "threshold": 100},
    {"id": "flashcards_500", "title": "Memória de aço", "description": "Revisou 500 flashcards", "icon": "🧬", "category": "flashcard", "threshold": 500},
    {"id": "mastered_10", "title": "Domínio total", "description": "Dominou 10 cards (intervalo > 21 dias)", "icon": "👑", "category": "flashcard", "threshold": 10},
    {"id": "mastered_50", "title": "Mestre das cartas", "description": "Dominou 50 cards", "icon": "🏅", "category": "flashcard", "threshold": 50},
    {"id": "first_plan", "title": "Planejador", "description": "Criou o primeiro plano de estudo", "icon": "📋", "category": "study_plan", "threshold": 1},
    {"id": "plan_completed", "title": "Conquistador", "description": "Completou um plano de estudo 100%", "icon": "🎖️", "category": "study_plan", "threshold": 1},
    {"id": "plans_5", "title": "Estrategista", "description": "Completou 5 planos de estudo", "icon": "⚡", "category": "study_plan", "threshold": 5},
    {"id": "plans_10", "title": "General", "description": "Completou 10 planos de estudo", "icon": "🏅", "category": "study_plan", "threshold": 10},
    {"id": "topics_5", "title": "Explorador", "description": "Estudou 5 temas diferentes", "icon": "🗺️", "category": "mastery", "threshold": 5},
    {"id": "topics_10", "title": "Polímata", "description": "Estudou 10 temas diferentes", "icon": "🎓", "category": "mastery", "threshold": 10},
    {"id": "topics_20", "title": "Sabiás", "description": "Estudou 20 temas diferentes", "icon": "🏛️", "category": "mastery", "threshold": 20},
    {"id": "weak_to_strong", "title": "Virada de jogo", "description": "Melhorou um tema de fraco para forte", "icon": "💪", "category": "mastery", "threshold": 1},
    {"id": "all_strong", "title": "Dominador", "description": "Todos os temas estudados estão fortes", "icon": "🌍", "category": "mastery", "threshold": 1},
    {"id": "level_estudante", "title": "Nível Estudante", "description": "Alcançou o nível Estudante", "icon": "📖", "category": "level", "threshold": 100},
    {"id": "level_graduado", "title": "Nível Graduado", "description": "Alcançou o nível Graduado", "icon": "🎓", "category": "level", "threshold": 300},
    {"id": "level_especialista", "title": "Nível Especialista", "description": "Alcançou o nível Especialista", "icon": "⚡", "category": "level", "threshold": 600},
    {"id": "level_mestre", "title": "Nível Mestre", "description": "Alcançou o nível Mestre", "icon": "👑", "category": "level", "threshold": 1000},
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
    if aid == "exercises_100":
        return conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0] >= 100
    if aid == "perfect_score":
        return conn.execute("SELECT COUNT(*) FROM exercise_history WHERE percent = 100").fetchone()[0] >= 1
    if aid == "streak_3":
        return _current_streak(conn) >= 3
    if aid == "streak_7":
        return _current_streak(conn) >= 7
    if aid == "streak_14":
        return _current_streak(conn) >= 14
    if aid == "streak_30":
        return _current_streak(conn) >= 30
    if aid == "first_flashcard":
        return conn.execute("SELECT COUNT(*) FROM flashcard_decks").fetchone()[0] >= 1
    if aid == "flashcards_100":
        return conn.execute("SELECT COUNT(*) FROM flashcard_reviews").fetchone()[0] >= 100
    if aid == "flashcards_500":
        return conn.execute("SELECT COUNT(*) FROM flashcard_reviews").fetchone()[0] >= 500
    if aid == "mastered_10":
        return conn.execute("SELECT COUNT(*) FROM flashcards WHERE interval_days >= 21").fetchone()[0] >= 10
    if aid == "mastered_50":
        return conn.execute("SELECT COUNT(*) FROM flashcards WHERE interval_days >= 21").fetchone()[0] >= 50
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
    if aid == "plans_10":
        return conn.execute(
            "SELECT COUNT(*) FROM study_plans WHERE total_items > 0 AND done_items = total_items"
        ).fetchone()[0] >= 10
    if aid == "topics_5":
        return conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0] >= 5
    if aid == "topics_10":
        return conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0] >= 10
    if aid == "topics_20":
        return conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0] >= 20
    if aid == "weak_to_strong":
        return conn.execute(
            "SELECT COUNT(*) FROM topic_mastery WHERE weighted_score >= 80 AND attempts >= 2"
        ).fetchone()[0] >= 1
    if aid == "all_strong":
        total = conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0]
        if total == 0:
            return False
        strong = conn.execute(
            "SELECT COUNT(*) FROM topic_mastery WHERE weighted_score >= 80 AND attempts >= 2"
        ).fetchone()[0]
        return strong == total
    if aid.startswith("level_"):
        level_name = aid.replace("level_", "").capitalize()
        level_map = {"Iniciante": 0, "Estudante": 1, "Graduado": 2, "Especialista": 3, "Mestre": 4}
        current = _get_level(conn)
        return level_map.get(current, 0) >= level_map.get(level_name, 99)
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


def _ensure_level_row(conn) -> None:
    row = conn.execute("SELECT id FROM student_level WHERE id = 1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO student_level (id, level, total_xp, updated_at) VALUES (1, 'Iniciante', 0, ?)",
            (datetime.now().isoformat(),),
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
        "exercises_100": {"current": exercise_count, "target": 100},
        "perfect_score": {"current": perfect_count, "target": 1},
        "streak_3": {"current": streak, "target": 3},
        "streak_7": {"current": streak, "target": 7},
        "streak_14": {"current": streak, "target": 14},
        "streak_30": {"current": streak, "target": 30},
        "first_flashcard": {"current": deck_count, "target": 1},
        "flashcards_100": {"current": review_count, "target": 100},
        "flashcards_500": {"current": review_count, "target": 500},
        "mastered_10": {"current": mastered_count, "target": 10},
        "mastered_50": {"current": mastered_count, "target": 50},
        "first_plan": {"current": plan_count, "target": 1},
        "plan_completed": {"current": completed_plans, "target": 1},
        "plans_5": {"current": completed_plans, "target": 5},
        "plans_10": {"current": completed_plans, "target": 10},
        "topics_5": {"current": topic_count, "target": 5},
        "topics_10": {"current": topic_count, "target": 10},
        "topics_20": {"current": topic_count, "target": 20},
        "weak_to_strong": {"current": strong_count, "target": 1},
        "all_strong": {"current": strong_count, "target": max(topic_count, 1)},
        "level_estudante": {"current": _get_total_xp(conn), "target": 100},
        "level_graduado": {"current": _get_total_xp(conn), "target": 300},
        "level_especialista": {"current": _get_total_xp(conn), "target": 600},
        "level_mestre": {"current": _get_total_xp(conn), "target": 1000},
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


# ── XP System ───────────────────────────────────────────────────────────────────


def award_xp(amount: int, source: str, description: str = "") -> dict:
    conn = get_connection()
    now = datetime.now().isoformat()
    _ensure_level_row(conn)
    conn.execute(
        "INSERT INTO student_xp (amount, source, description, created_at) VALUES (?, ?, ?, ?)",
        (amount, source, description, now),
    )
    conn.execute("UPDATE student_level SET total_xp = total_xp + ?, updated_at = ?", (amount, now))
    conn.commit()
    level_info = get_level_info()
    check_achievements()
    return {"xp_gained": amount, "source": source, **level_info}


def award_exercise_xp(correct: int, total: int, difficulty: str = "médio") -> dict:
    if total == 0:
        return {"xp_gained": 0}
    pct = correct / total
    base = {"muito fácil": 5, "fácil": 8, "médio": 12, "difícil": 18, "muito difícil": 25}
    xp = base.get(difficulty, 12)
    if pct >= 0.9:
        xp = int(xp * 1.5)
    elif pct >= 0.7:
        xp = int(xp * 1.2)
    elif pct < 0.4:
        xp = max(3, xp // 2)
    return award_xp(xp, "exercise", f"{correct}/{total} em {difficulty}")


def award_flashcard_xp(correct: bool) -> dict:
    xp = 5 if correct else 2
    return award_xp(xp, "flashcard", "revisão de flashcard")


def award_streak_xp(streak: int) -> dict:
    if streak < 3:
        return {"xp_gained": 0}
    xp = min(streak * 2, 30)
    return award_xp(xp, "streak", f"sequência de {streak} dias")


def award_plan_xp(completed: bool) -> dict:
    if not completed:
        return {"xp_gained": 0}
    return award_xp(50, "study_plan", "plano concluído")


# ── Level System ────────────────────────────────────────────────────────────────


def _get_total_xp(conn) -> int:
    row = conn.execute("SELECT total_xp FROM student_level WHERE id = 1").fetchone()
    return row[0] if row else 0


def _get_level(conn) -> str:
    row = conn.execute("SELECT level FROM student_level WHERE id = 1").fetchone()
    return row[0] if row else "Iniciante"


def _calculate_level(total_xp: int) -> str:
    level = "Iniciante"
    for name, threshold in LEVEL_THRESHOLDS:
        if total_xp >= threshold:
            level = name
    return level


def get_level_info() -> dict:
    conn = get_connection()
    row = conn.execute("SELECT level, total_xp FROM student_level WHERE id = 1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO student_level (id, level, total_xp, updated_at) VALUES (1, 'Iniciante', 0, ?)",
            (datetime.now().isoformat(),),
        )
        conn.commit()
        return {"level": "Iniciante", "total_xp": 0, "xp_to_next": 100, "next_level": "Estudante", "progress_percent": 0, "icon": "🌱"}

    level, total_xp = row[0], row[1]
    next_level = None
    for name, threshold in LEVEL_THRESHOLDS:
        if total_xp < threshold:
            next_level = (name, threshold)
            break

    if next_level is None:
        new_level = _calculate_level(total_xp)
        if new_level != level:
            conn.execute(
                "UPDATE student_level SET level = ?, updated_at = ? WHERE id = 1",
                (new_level, datetime.now().isoformat()),
            )
            conn.commit()
            level = new_level
        return {"level": level, "total_xp": total_xp, "xp_to_next": 0, "next_level": None, "progress_percent": 100, "icon": LEVEL_ICONS.get(level, "🌱")}

    prev_threshold = 0
    for name, threshold in LEVEL_THRESHOLDS:
        if name == next_level[0]:
            break
        prev_threshold = threshold

    level_range = next_level[1] - prev_threshold
    in_level = total_xp - prev_threshold
    progress = min(100, round(100 * in_level / max(level_range, 1)))

    new_level = _calculate_level(total_xp)
    if new_level != level:
        conn.execute(
            "UPDATE student_level SET level = ?, updated_at = ? WHERE id = 1",
            (new_level, datetime.now().isoformat()),
        )
        conn.commit()
        level = new_level

    return {
        "level": level,
        "total_xp": total_xp,
        "xp_to_next": next_level[1] - total_xp,
        "next_level": next_level[0],
        "progress_percent": progress,
        "icon": LEVEL_ICONS.get(level, "🌱"),
    }


# ── Leaderboard ─────────────────────────────────────────────────────────────────


def leaderboard(limit: int = 20) -> dict:
    conn = get_connection()
    level_info = get_level_info()

    achievements_earned = conn.execute("SELECT COUNT(*) FROM achievements").fetchone()[0]
    total_achievements = len(ACHIEVEMENT_DEFS)

    streak = _current_streak(conn)
    exercises = conn.execute("SELECT COUNT(*) FROM exercise_history").fetchone()[0]
    flashcard_reviews = conn.execute("SELECT COUNT(*) FROM flashcard_reviews").fetchone()[0]
    topics_mastered = conn.execute(
        "SELECT COUNT(*) FROM topic_mastery WHERE weighted_score >= 80 AND attempts >= 2"
    ).fetchone()[0]

    weekly_xp = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM student_xp WHERE created_at >= ?",
        ((datetime.now() - timedelta(days=7)).isoformat(),),
    ).fetchone()[0]

    recent_activity = conn.execute(
        "SELECT amount, source, description, created_at FROM student_xp ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    return {
        **level_info,
        "achievements_earned": achievements_earned,
        "total_achievements": total_achievements,
        "current_streak": streak,
        "total_exercises": exercises,
        "total_flashcard_reviews": flashcard_reviews,
        "topics_mastered": topics_mastered,
        "weekly_xp": weekly_xp,
        "recent_activity": [dict(r) for r in recent_activity],
    }


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
