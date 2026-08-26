"""Perfil avançado: sessões de estudo, analytics temporal, dificuldade adaptativa.

Registra sessões de estudo com duração, analisa horários ideais,
e ajusta dificuldade automaticamente com base no desempenho.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from ..db import get_connection

LEVELS = ["muito fácil", "fácil", "médio", "difícil", "muito difícil"]
LEVEL_MAP = {lvl: i for i, lvl in enumerate(LEVELS)}
WINDOW_SIZE = 5


# ── Session Log ─────────────────────────────────────────────────────────────────


def start_session(session_type: str, metadata: dict | None = None) -> str:
    session_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO session_log (id, session_type, started_at, metadata) VALUES (?, ?, ?, ?)",
        (session_id, session_type, now, json.dumps(metadata or {}, ensure_ascii=False)),
    )
    conn.commit()
    return session_id


def end_session(session_id: str) -> dict:
    now = datetime.now()
    now_iso = now.isoformat()
    conn = get_connection()
    row = conn.execute("SELECT * FROM session_log WHERE id = ?", (session_id,)).fetchone()
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
    return {"id": session_id, "duration_seconds": duration}


def time_analytics() -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT session_type, started_at, duration_seconds FROM session_log "
        "WHERE duration_seconds IS NOT NULL AND duration_seconds >= 0"
    ).fetchall()

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
    conn = get_connection()
    now = datetime.now().isoformat()
    due_count = conn.execute(
        "SELECT COUNT(*) FROM flashcards WHERE next_review <= ?", (now,)
    ).fetchone()[0]

    pending_items = conn.execute(
        "SELECT si.title, si.detail, sp.title as plan_title "
        "FROM study_items si JOIN study_plans sp ON si.plan_id = sp.id "
        "WHERE si.done = 0 ORDER BY si.sort_order LIMIT ?",
        (max(1, minutes // 5),),
    ).fetchall()

    weak = conn.execute(
        "SELECT topic, weighted_score, avg_percent FROM topic_mastery "
        "WHERE weighted_score < 55 AND attempts >= 2 ORDER BY weighted_score ASC LIMIT 3",
    ).fetchall()

    suggestions = []
    if due_count > 0:
        cards_time = min(due_count * 1, minutes)
        suggestions.append({
            "type": "flashcards",
            "description": f"Revisar {min(due_count, minutes)} flashcards pendentes",
            "estimated_minutes": cards_time,
            "priority": "alta",
        })

    if weak:
        for w in weak:
            w = dict(w)
            ws = w.get("weighted_score") or w["avg_percent"]
            suggestions.append({
                "type": "exercise",
                "description": f"Fazer exercícios de {w['topic']} (mastery: {ws}%)",
                "estimated_minutes": min(15, minutes),
                "priority": "alta" if ws < 40 else "média",
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
    conn = get_connection()
    row = conn.execute("SELECT * FROM adaptive_difficulty WHERE topic = ?", (topic,)).fetchone()
    if row:
        return dict(row)
    return {"topic": topic, "current_level": "médio", "window_avg": 50.0, "window_count": 0}


def update_difficulty(topic: str, percent: int) -> dict:
    conn = get_connection()
    now = datetime.now().isoformat()

    # Real rolling window: get last WINDOW_SIZE results from topic_results
    rows = conn.execute(
        "SELECT percent FROM topic_results WHERE topic = ? ORDER BY created_at DESC LIMIT ?",
        (topic, WINDOW_SIZE),
    ).fetchall()

    if rows:
        percents = [r["percent"] for r in rows]
        new_avg = sum(percents) / len(percents)
        new_count = len(percents)
    else:
        new_avg = float(percent)
        new_count = 1

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

    row = conn.execute("SELECT * FROM adaptive_difficulty WHERE topic = ?", (topic,)).fetchone()
    if row:
        conn.execute(
            "UPDATE adaptive_difficulty SET current_level=?, window_avg=?, window_count=?, updated_at=? WHERE topic=?",
            (level, round(new_avg, 1), new_count, now, topic),
        )
    else:
        conn.execute(
            "INSERT INTO adaptive_difficulty (topic, current_level, window_avg, window_count, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (topic, level, round(new_avg, 1), new_count, now),
        )
    conn.commit()
    return {"topic": topic, "current_level": level, "window_avg": round(new_avg, 1)}


def difficulty_for_generation(topic: str) -> str:
    diff = get_adaptive_difficulty(topic)
    return diff["current_level"]
