"""Perfil do aluno e dominância por tema com scoring ponderado.

Analisa histórico de exercícios, flashcards e planos para detectar
pontos fracos/fortes e sugerir revisões. Usa weighted scoring que
considera dificuldade, consistência, recência e volume.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from ..db import get_connection

WEAK_THRESHOLD = 55
STRONG_THRESHOLD = 80
MIN_ATTEMPTS = 2

SCORING_WEIGHTS = {
    "difficulty": 0.30,
    "consistency": 0.25,
    "recency": 0.25,
    "volume": 0.20,
}

DIFFICULTY_SCORES = {
    "muito fácil": 20,
    "fácil": 40,
    "médio": 60,
    "difícil": 80,
    "muito difícil": 100,
}

RECENCY_HALF_LIFE_DAYS = 7


# ── Profile CRUD ───────────────────────────────────────────────────────────────


def get_profile() -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM student_profile LIMIT 1").fetchone()
    return dict(row) if row else None


def save_profile(name: str = "", grade: str = "", school: str = "", preferences: str = "") -> dict:
    conn = get_connection()
    existing = conn.execute("SELECT id FROM student_profile LIMIT 1").fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            "UPDATE student_profile SET name=?, grade=?, school=?, preferences=?, updated_at=? "
            "WHERE id=?",
            (name, grade, school, preferences, now, existing["id"]),
        )
        profile_id = existing["id"]
    else:
        profile_id = "student1"
        conn.execute(
            "INSERT INTO student_profile (id, name, grade, school, preferences, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (profile_id, name, grade, school, preferences, now, now),
        )
    conn.commit()
    return {"id": profile_id, "name": name, "grade": grade, "school": school, "preferences": preferences}


# ── Weighted Scoring ───────────────────────────────────────────────────────────


def calculate_weighted_score(topic: str) -> float:
    """Calculate weighted mastery score from individual results.

    Combines 4 factors:
    - difficulty (30%): average difficulty level of exercises attempted
    - consistency (25%): low variance = high consistency
    - recency (25%): recent results weighted more (exponential decay)
    - volume (20%): more attempts = more confidence (capped at 20)
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT percent, difficulty_level, created_at FROM topic_results "
        "WHERE topic = ? ORDER BY created_at DESC LIMIT 20",
        (topic,),
    ).fetchall()

    if not rows:
        return 0.0

    results = [dict(r) for r in rows]
    percents = [r["percent"] for r in results]

    # 1. Difficulty factor (0-100)
    diff_values = [DIFFICULTY_SCORES.get(r["difficulty_level"], 60) for r in results]
    avg_difficulty = sum(diff_values) / len(diff_values)

    # 2. Consistency factor (0-100)
    avg_pct = sum(percents) / len(percents)
    if len(percents) > 1:
        variance = sum((p - avg_pct) ** 2 for p in percents) / len(percents)
        std_dev = math.sqrt(variance)
        consistency = max(0.0, 100.0 - std_dev * 2)
    else:
        consistency = 50.0

    # 3. Recency factor (0-100)
    now = datetime.now()
    decay_rate = math.log(2) / RECENCY_HALF_LIFE_DAYS
    weighted_sum = 0.0
    weight_sum = 0.0
    for r in results:
        try:
            days_ago = (now - datetime.fromisoformat(r["created_at"])).total_seconds() / 86400
        except (ValueError, TypeError):
            days_ago = 30
        w = math.exp(-decay_rate * days_ago)
        weighted_sum += r["percent"] * w
        weight_sum += w
    recency = weighted_sum / weight_sum if weight_sum > 0 else avg_pct

    # 4. Volume factor (0-100)
    volume = min(100.0, len(results) * 5.0)

    weighted = (
        avg_difficulty * SCORING_WEIGHTS["difficulty"]
        + consistency * SCORING_WEIGHTS["consistency"]
        + recency * SCORING_WEIGHTS["recency"]
        + volume * SCORING_WEIGHTS["volume"]
    )

    return round(weighted, 1)


def _recalculate_weighted_score(conn, topic: str) -> None:
    """Recalculate and update weighted_score for a topic."""
    score = 0.0
    rows = conn.execute(
        "SELECT percent, difficulty_level, created_at FROM topic_results "
        "WHERE topic = ? ORDER BY created_at DESC LIMIT 20",
        (topic,),
    ).fetchall()
    if rows:
        results = [dict(r) for r in rows]
        percents = [r["percent"] for r in results]

        diff_values = [DIFFICULTY_SCORES.get(r["difficulty_level"], 60) for r in results]
        avg_difficulty = sum(diff_values) / len(diff_values)

        avg_pct = sum(percents) / len(percents)
        if len(percents) > 1:
            variance = sum((p - avg_pct) ** 2 for p in percents) / len(percents)
            std_dev = math.sqrt(variance)
            consistency = max(0.0, 100.0 - std_dev * 2)
        else:
            consistency = 50.0

        now = datetime.now()
        decay_rate = math.log(2) / RECENCY_HALF_LIFE_DAYS
        weighted_sum = 0.0
        weight_sum = 0.0
        for r in results:
            try:
                days_ago = (now - datetime.fromisoformat(r["created_at"])).total_seconds() / 86400
            except (ValueError, TypeError):
                days_ago = 30
            w = math.exp(-decay_rate * days_ago)
            weighted_sum += r["percent"] * w
            weight_sum += w
        recency = weighted_sum / weight_sum if weight_sum > 0 else avg_pct

        volume = min(100.0, len(results) * 5.0)

        score = round(
            avg_difficulty * SCORING_WEIGHTS["difficulty"]
            + consistency * SCORING_WEIGHTS["consistency"]
            + recency * SCORING_WEIGHTS["recency"]
            + volume * SCORING_WEIGHTS["volume"],
            1,
        )

    conn.execute(
        "UPDATE topic_mastery SET weighted_score=? WHERE topic=?",
        (score, topic),
    )


# ── Topic Mastery ──────────────────────────────────────────────────────────────


def update_from_exercise(topic: str, score: int, total: int, percent: int, difficulty_level: str = "médio") -> None:
    conn = get_connection()
    now = datetime.now().isoformat()

    # Insert individual result for rolling window
    conn.execute(
        "INSERT INTO topic_results (topic, percent, difficulty_level, created_at) VALUES (?, ?, ?, ?)",
        (topic, percent, difficulty_level, now),
    )

    # Update aggregate mastery
    row = conn.execute("SELECT * FROM topic_mastery WHERE topic = ?", (topic,)).fetchone()
    if row:
        row = dict(row)
        attempts = row["attempts"] + 1
        correct = row["correct"] + score
        total_q = row["total_questions"] + total
        avg = round(100 * correct / max(total_q, 1))
        conn.execute(
            "UPDATE topic_mastery SET attempts=?, correct=?, total_questions=?, "
            "avg_percent=?, last_practiced=?, updated_at=? WHERE topic=?",
            (attempts, correct, total_q, avg, now, now, topic),
        )
    else:
        conn.execute(
            "INSERT INTO topic_mastery "
            "(topic, attempts, correct, total_questions, avg_percent, weighted_score, last_practiced, created_at, updated_at) "
            "VALUES (?, 1, ?, ?, ?, 0.0, ?, ?, ?)",
            (topic, score, total, percent, now, now, now),
        )

    _recalculate_weighted_score(conn, topic)
    conn.commit()


def update_from_flashcard_review(topic: str, quality: int) -> None:
    correct = 1 if quality >= 3 else 0
    pct = 100 if correct else 0

    conn = get_connection()
    now = datetime.now().isoformat()

    # Insert individual result
    conn.execute(
        "INSERT INTO topic_results (topic, percent, difficulty_level, created_at) VALUES (?, ?, ?, ?)",
        (topic, pct, "médio", now),
    )

    row = conn.execute("SELECT * FROM topic_mastery WHERE topic = ?", (topic,)).fetchone()
    if row:
        row = dict(row)
        attempts = row["attempts"] + 1
        correct_total = row["correct"] + correct
        total_q = row["total_questions"] + 1
        avg = round(100 * correct_total / max(total_q, 1))
        conn.execute(
            "UPDATE topic_mastery SET attempts=?, correct=?, total_questions=?, "
            "avg_percent=?, last_practiced=?, updated_at=? WHERE topic=?",
            (attempts, correct_total, total_q, avg, now, now, topic),
        )
    else:
        conn.execute(
            "INSERT INTO topic_mastery "
            "(topic, attempts, correct, total_questions, avg_percent, weighted_score, last_practiced, created_at, updated_at) "
            "VALUES (?, 1, ?, 1, ?, 0.0, ?, ?, ?)",
            (topic, correct, pct, now, now, now),
        )

    _recalculate_weighted_score(conn, topic)
    conn.commit()


def classify_topics() -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM topic_mastery WHERE attempts >= ? ORDER BY weighted_score ASC",
        (MIN_ATTEMPTS,),
    ).fetchall()

    weak, strong, neutral = [], [], []
    for r in rows:
        r = dict(r)
        entry = {
            "topic": r["topic"],
            "avg_percent": r["avg_percent"],
            "weighted_score": r.get("weighted_score") or r["avg_percent"],
            "attempts": r["attempts"],
        }
        ws = entry["weighted_score"]
        if ws < WEAK_THRESHOLD:
            weak.append(entry)
        elif ws >= STRONG_THRESHOLD:
            strong.append(entry)
        else:
            neutral.append(entry)

    return {"weak": weak, "strong": strong, "neutral": neutral}


def suggest_review() -> list[dict]:
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=3)).isoformat()
    rows = conn.execute(
        "SELECT * FROM topic_mastery "
        "WHERE weighted_score < ? OR (attempts >= ? AND last_practiced < ?) "
        "ORDER BY weighted_score ASC LIMIT 5",
        (STRONG_THRESHOLD, MIN_ATTEMPTS, cutoff),
    ).fetchall()
    return [dict(r) for r in rows]


def topic_details(topic: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM topic_mastery WHERE topic = ?", (topic,)).fetchone()
    return dict(row) if row else None


def all_mastery() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM topic_mastery ORDER BY weighted_score ASC").fetchall()
    return [dict(r) for r in rows]


def profile_insights() -> dict:
    profile = get_profile()
    classification = classify_topics()
    suggestions = suggest_review()
    return {
        "profile": profile,
        "weak_topics": classification["weak"],
        "strong_topics": classification["strong"],
        "suggestions": [{"topic": s["topic"], "weighted_score": s.get("weighted_score") or s["avg_percent"]} for s in suggestions],
        "total_topics_studied": sum(
            len(classification[k]) for k in ("weak", "strong", "neutral")
        ),
    }


def student_dashboard() -> str:
    """Build a concise student state summary for the system prompt.

    Returns a formatted string with mastery overview, recent activity,
    and streak — designed to be injected into the system prompt.
    """
    conn = get_connection()

    weak = conn.execute(
        "SELECT topic, weighted_score FROM topic_mastery "
        "WHERE weighted_score < ? AND attempts >= ? "
        "ORDER BY weighted_score ASC LIMIT 3",
        (WEAK_THRESHOLD, MIN_ATTEMPTS),
    ).fetchall()

    strong = conn.execute(
        "SELECT topic, weighted_score FROM topic_mastery "
        "WHERE weighted_score >= ? AND attempts >= ? "
        "ORDER BY weighted_score DESC LIMIT 3",
        (STRONG_THRESHOLD, MIN_ATTEMPTS),
    ).fetchall()

    recent = conn.execute(
        "SELECT topic, percent, created_at FROM topic_results "
        "ORDER BY created_at DESC LIMIT 3",
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM topic_mastery").fetchone()[0]

    streak = 0
    today = datetime.now().date()
    for offset in range(30):
        day = (today - timedelta(days=offset)).isoformat()
        has = conn.execute(
            "SELECT 1 FROM topic_results WHERE date(created_at) = ? LIMIT 1", (day,)
        ).fetchone()
        if has:
            streak += 1
        elif offset > 0:
            break

    if not weak and not strong and not recent:
        return ""

    lines = ["Dashboard do aluno:"]

    if weak:
        items = ", ".join(f"{r['topic']} ({r['weighted_score']}%)" for r in weak)
        lines.append(f"- Pontos fracos: {items}")

    if strong:
        items = ", ".join(f"{r['topic']} ({r['weighted_score']}%)" for r in strong)
        lines.append(f"- Fortes: {items}")

    if recent:
        items = ", ".join(f"{r['topic']} {r['percent']}%" for r in recent)
        lines.append(f"- Últimos exercícios: {items}")

    lines.append(f"- Temas estudados: {total} | Streak: {streak} dias")

    return "\n".join(lines)
