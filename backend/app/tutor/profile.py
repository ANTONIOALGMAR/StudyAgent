"""Perfil do aluno e dominância por tema.

Analisa histórico de exercícios, flashcards e planos para detectar
pontos fracos/fortes e sugerir revisões. Tudo em SQLite puro.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..config import MEMORY_DB_PATH

WEAK_THRESHOLD = 55     # avg_percent abaixo disso = ponto fraco
STRONG_THRESHOLD = 80   # avg_percent acima disso = ponto forte
MIN_ATTEMPTS = 2        # tentativas mínimas para classificar


def _conn():
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Profile CRUD ───────────────────────────────────────────────────────────────


def get_profile() -> dict | None:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM student_profile LIMIT 1").fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def save_profile(name: str = "", grade: str = "", school: str = "", preferences: str = "") -> dict:
    conn = _conn()
    try:
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
    finally:
        conn.close()
    return {"id": profile_id, "name": name, "grade": grade, "school": school, "preferences": preferences}


# ── Topic Mastery ──────────────────────────────────────────────────────────────


def update_from_exercise(topic: str, score: int, total: int, percent: int) -> None:
    """Update topic mastery after an exercise is graded."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM topic_mastery WHERE topic = ?", (topic,)
        ).fetchone()
        now = datetime.now().isoformat()
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
                "(topic, attempts, correct, total_questions, avg_percent, last_practiced, created_at, updated_at) "
                "VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
                (topic, score, total, percent, now, now, now),
            )
        conn.commit()
    finally:
        conn.close()


def update_from_flashcard_review(topic: str, quality: int) -> None:
    """Update topic mastery from flashcard review (quality 0-5)."""
    correct = 1 if quality >= 3 else 0
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM topic_mastery WHERE topic = ?", (topic,)
        ).fetchone()
        now = datetime.now().isoformat()
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
            pct = 100 if correct else 0
            conn.execute(
                "INSERT INTO topic_mastery "
                "(topic, attempts, correct, total_questions, avg_percent, last_practiced, created_at, updated_at) "
                "VALUES (?, 1, ?, 1, ?, ?, ?, ?)",
                (topic, correct, pct, now, now, now),
            )
        conn.commit()
    finally:
        conn.close()


def classify_topics() -> dict:
    """Classify all topics into weak/strong/neutral."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM topic_mastery WHERE attempts >= ? ORDER BY avg_percent ASC",
            (MIN_ATTEMPTS,),
        ).fetchall()
    finally:
        conn.close()

    weak, strong, neutral = [], [], []
    for r in rows:
        r = dict(r)
        entry = {"topic": r["topic"], "avg_percent": r["avg_percent"], "attempts": r["attempts"]}
        if r["avg_percent"] < WEAK_THRESHOLD:
            weak.append(entry)
        elif r["avg_percent"] >= STRONG_THRESHOLD:
            strong.append(entry)
        else:
            neutral.append(entry)

    return {"weak": weak, "strong": strong, "neutral": neutral}


def suggest_review() -> list[dict]:
    """Suggest topics that need review (weak + not practiced in 3+ days)."""
    conn = _conn()
    try:
        cutoff = (datetime.now() - timedelta(days=3)).isoformat()
        rows = conn.execute(
            "SELECT * FROM topic_mastery "
            "WHERE avg_percent < ? OR (attempts >= ? AND last_practiced < ?) "
            "ORDER BY avg_percent ASC LIMIT 5",
            (STRONG_THRESHOLD, MIN_ATTEMPTS, cutoff),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def topic_details(topic: str) -> dict | None:
    """Detailed mastery for a specific topic."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM topic_mastery WHERE topic = ?", (topic,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def all_mastery() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM topic_mastery ORDER BY avg_percent ASC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def profile_insights() -> dict:
    """Combined profile + mastery insights for the agent context."""
    profile = get_profile()
    classification = classify_topics()
    suggestions = suggest_review()
    return {
        "profile": profile,
        "weak_topics": classification["weak"],
        "strong_topics": classification["strong"],
        "suggestions": [{"topic": s["topic"], "avg_percent": s["avg_percent"]} for s in suggestions],
        "total_topics_studied": sum(
            len(classification[k]) for k in ("weak", "strong", "neutral")
        ),
    }
