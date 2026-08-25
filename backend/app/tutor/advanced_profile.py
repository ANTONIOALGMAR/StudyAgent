"""Perfil avançado: sessões de estudo, analytics temporal, dificuldade adaptativa.

Registra sessões de estudo com duração, analisa horários ideais,
e ajusta dificuldade automaticamente com base no desempenho.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime

from ..config import MEMORY_DB_PATH

# ── Difficulty levels ────────────────────────────────────────────────────────────

LEVELS = ["muito fácil", "fácil", "médio", "difícil", "muito difícil"]
LEVEL_MAP = {lvl: i for i, lvl in enumerate(LEVELS)}
WINDOW_SIZE = 5  # last N exercises to consider for difficulty


def _conn():
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Session Log ─────────────────────────────────────────────────────────────────


def start_session(session_type: str, metadata: dict | None = None) -> str:
    """Log the start of a study session. Returns session_log_id."""
    session_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO session_log (id, session_type, started_at, metadata) "
            "VALUES (?, ?, ?, ?)",
            (session_id, session_type, now, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return session_id


def end_session(session_id: str) -> dict:
    """End a session, compute duration."""
    now = datetime.now()
    now_iso = now.isoformat()
    conn = _conn()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM session_log WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Sessão {session_id} não encontrada")
        session = dict(row)
        if session["ended_at"]:
            return {"id": session_id, "duration_seconds": session["duration_seconds"]}
        started = datetime.fromisoformat(session["started_at"])
        duration = int((now - started).total_seconds())
        conn.execute(
            "UPDATE session_log SET ended_at = ?, duration_seconds = ? WHERE id = ?",
            (now_iso, duration, session_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": session_id, "duration_seconds": duration}


def time_analytics() -> dict:
    """Analyze study patterns: best hours, avg session length, sessions per type."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT session_type, started_at, duration_seconds FROM session_log "
            "WHERE duration_seconds IS NOT NULL AND duration_seconds >= 0"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "total_sessions": 0,
            "total_study_minutes": 0,
            "avg_session_minutes": 0,
            "best_hours": [],
            "by_type": {},
        }

    total_seconds = 0
    hour_counts: dict[int, int] = {}
    by_type: dict[str, dict] = {}

    for r in rows:
        r = dict(r)
        dur = r["duration_seconds"]
        total_seconds += dur

        hour = datetime.fromisoformat(r["started_at"]).hour
        hour_counts[hour] = hour_counts.get(hour, 0) + 1

        stype = r["session_type"]
        if stype not in by_type:
            by_type[stype] = {"count": 0, "total_seconds": 0}
        by_type[stype]["count"] += 1
        by_type[stype]["total_seconds"] += dur

    best_hours = sorted(hour_counts, key=lambda h: hour_counts[h], reverse=True)[:3]

    avg_seconds = total_seconds / len(rows)
    type_summary = {}
    for k, v in by_type.items():
        type_summary[k] = {
            "count": v["count"],
            "avg_minutes": round(v["total_seconds"] / v["count"] / 60, 1),
        }

    return {
        "total_sessions": len(rows),
        "total_study_minutes": round(total_seconds / 60),
        "avg_session_minutes": round(avg_seconds / 60, 1),
        "best_hours": [{"hour": h, "sessions": hour_counts[h]} for h in best_hours],
        "by_type": type_summary,
    }


def recommend_for_time(minutes: int) -> dict:
    """Recommend what to study given a time budget (in minutes)."""
    conn = _conn()
    try:
        # Check due flashcards
        now = datetime.now().isoformat()
        due_count = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE next_review <= ?", (now,)
        ).fetchone()[0]

        # Check pending plan items
        pending_items = conn.execute(
            "SELECT si.title, si.detail, sp.title as plan_title "
            "FROM study_items si JOIN study_plans sp ON si.plan_id = sp.id "
            "WHERE si.done = 0 ORDER BY si.sort_order LIMIT ?",
            (max(1, minutes // 5),),
        ).fetchall()

        # Check weak topics for exercises
        weak = conn.execute(
            "SELECT topic, avg_percent FROM topic_mastery "
            "WHERE avg_percent < 55 AND attempts >= 2 "
            "ORDER BY avg_percent ASC LIMIT 3",
        ).fetchall()

    finally:
        conn.close()

    suggestions = []

    if due_count > 0:
        cards_time = min(due_count * 1, minutes)  # ~1 min per card
        suggestions.append({
            "type": "flashcards",
            "description": f"Revisar {min(due_count, minutes)} flashcards pendentes",
            "estimated_minutes": cards_time,
            "priority": "alta",
        })

    if weak:
        for w in weak:
            w = dict(w)
            suggestions.append({
                "type": "exercise",
                "description": f"Fazer exercícios de {w['topic']} (média: {w['avg_percent']}%)",
                "estimated_minutes": min(15, minutes),
                "priority": "alta" if w["avg_percent"] < 40 else "média",
            })

    if pending_items:
        items_desc = [dict(it)["title"] for it in pending_items[:3]]
        suggestions.append({
            "type": "study_plan",
            "description": f"Continuar plano: {', '.join(items_desc)}",
            "estimated_minutes": min(len(pending_items) * 5, minutes),
            "priority": "média",
        })

    if not suggestions:
        suggestions.append({
            "type": "free_study",
            "description": "Que tal revisar um tema ou gerar novos exercícios?",
            "estimated_minutes": minutes,
            "priority": "baixa",
        })

    return {
        "available_minutes": minutes,
        "suggestions": sorted(suggestions, key=lambda s: {"alta": 0, "média": 1, "baixa": 2}[s["priority"]]),
    }


# ── Adaptive Difficulty ─────────────────────────────────────────────────────────


def get_adaptive_difficulty(topic: str) -> dict:
    """Get current adaptive difficulty for a topic."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM adaptive_difficulty WHERE topic = ?", (topic,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "topic": topic,
            "current_level": "médio",
            "window_avg": 50.0,
            "window_count": 0,
        }
    finally:
        conn.close()


def update_difficulty(topic: str, percent: int) -> dict:
    """Update adaptive difficulty after an exercise result."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    now = datetime.now().isoformat()
    try:
        row = conn.execute(
            "SELECT * FROM adaptive_difficulty WHERE topic = ?", (topic,)
        ).fetchone()
        if row:
            row = dict(row)
            new_count = row["window_count"] + 1
            new_avg = ((row["window_avg"] * row["window_count"]) + percent) / new_count
            # Keep only last WINDOW_SIZE results (simple approach: just track avg)
            if new_count > WINDOW_SIZE:
                new_avg = (new_avg * (new_count - 1) + percent) / new_count
                new_count = min(new_count, WINDOW_SIZE + 1)
        else:
            new_avg = float(percent)
            new_count = 1

        # Map avg to level
        if new_avg < 30:
            level = "muito fácil"
        elif new_avg < 50:
            level = "fácil"
        elif new_avg < 70:
            level = "médio"
        elif new_avg < 85:
            level = "difícil"
        else:
            level = "muito difícil"

        if row:
            conn.execute(
                "UPDATE adaptive_difficulty SET current_level=?, window_avg=?, "
                "window_count=?, updated_at=? WHERE topic=?",
                (level, round(new_avg, 1), new_count, now, topic),
            )
        else:
            conn.execute(
                "INSERT INTO adaptive_difficulty (topic, current_level, window_avg, window_count, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (topic, level, round(new_avg, 1), new_count, now),
            )
        conn.commit()
    finally:
        conn.close()

    return {"topic": topic, "current_level": level, "window_avg": round(new_avg, 1)}


def difficulty_for_generation(topic: str) -> str:
    """Return the difficulty string to pass to exercise/flashcard generation."""
    diff = get_adaptive_difficulty(topic)
    return diff["current_level"]
