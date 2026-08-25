"""Flashcards com repetição espaçada SM-2 e geração via LLM.

Algoritmo SM-2 adaptado de Piotr Wozniak (25 Anki).
Armazenamento em SQLite via tabela flashcards + flashcard_reviews.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta

from ..agent.llm import chat
from ..config import MEMORY_DB_PATH

# ─── SM-2 constants ────────────────────────────────────────────────────────────
DEFAULT_EASINESS = 2.5
MIN_EASINESS = 1.3
INITIAL_INTERVAL_DAYS = 1


def sm2_next(easiness: float, interval: int, repetitions: int, quality: int) -> tuple[float, int, int]:
    """Calculate next (easiness, interval_days, repetitions) from a 0-5 rating.

    quality: 0=blackout, 1=wrong, 2=hard, 3=ok, 4=good, 5=perfect
    """
    quality = max(0, min(5, quality))
    easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    easiness = max(MIN_EASINESS, easiness)
    if quality < 3:
        repetitions = 0
        interval = INITIAL_INTERVAL_DAYS
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = max(1, round(interval * easiness))
    return easiness, interval, repetitions


def quality_from_difficulty(difficulty: str) -> int:
    """Map user-facing difficulty to SM-2 quality score."""
    mapping = {"again": 1, "hard": 2, "good": 3, "easy": 5}
    return mapping.get(difficulty, 3)


# ─── Flashcard CRUD ────────────────────────────────────────────────────────────

_GEN_PROMPT = (
    "Você é um criador de flashcards escolares brasileiros.\n"
    "Gere flashcards deface sobre: {topic}.\n"
    "Nível: {level}. Quantidade: {n} cards.\n"
    "Cada card deve ser curto e direto (1-2 frases no máximo por face).\n\n"
    'Responda ESTRITAMENTE neste JSON, sem texto fora dele:\n'
    '{{"cards": [{{"front": "pergunta curta", "back": "resposta curta"}}]}}'
)


def generate_deck(
    topic: str,
    n: int = 10,
    level: str = "ensino fundamental",
    source_doc: str | None = None,
    memory=None,
) -> dict:
    """Generate flashcards via LLM, store in SQLite, return deck info."""
    n = max(1, min(25, n))
    prompt = _GEN_PROMPT.format(topic=topic, n=n, level=level)
    raw = chat([{"role": "user", "content": prompt}])
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    cards_data = data.get("cards") or []

    deck_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()
    cards = []
    for c in cards_data[:n]:
        if not c.get("front") or not c.get("back"):
            continue
        cards.append(
            {
                "id": uuid.uuid4().hex[:8],
                "front": str(c["front"]),
                "back": str(c["back"]),
            }
        )

    if not cards:
        raise ValueError("O modelo não gerou flashcards válidos. Tente outro tema.")

    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    try:
        conn.execute(
            "INSERT INTO flashcard_decks (id, title, topic, source_doc, card_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (deck_id, topic, topic, source_doc, len(cards), now),
        )
        for card in cards:
            conn.execute(
                "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
                "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 1, 0, ?, ?)",
                (card["id"], deck_id, card["front"], card["back"], now, now),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "deck_id": deck_id,
        "topic": topic,
        "card_count": len(cards),
        "cards": cards,
    }


def due_cards(deck_id: str, limit: int = 20) -> list[dict]:
    """Cards due for review (next_review <= now), ordered by urgency."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM flashcards WHERE deck_id = ? AND next_review <= ? "
            "ORDER BY next_review ASC LIMIT ?",
            (deck_id, now, limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def list_decks() -> list[dict]:
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM flashcard_decks ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def review_card(card_id: str, difficulty: str) -> dict:
    """Record a review and schedule next occurrence."""
    quality = quality_from_difficulty(difficulty)
    now = datetime.now()
    now_iso = now.isoformat()

    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM flashcards WHERE id = ?", (card_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Flashcard {card_id} não encontrado")
        card = dict(row)
        new_easiness, new_interval, new_reps = sm2_next(
            card["easiness"], card["interval_days"], card["repetitions"], quality
        )
        next_review = (now + timedelta(days=new_interval)).isoformat()
        conn.execute(
            "UPDATE flashcards SET easiness=?, interval_days=?, repetitions=?, next_review=? "
            "WHERE id=?",
            (new_easiness, new_interval, new_reps, next_review, card_id),
        )
        conn.execute(
            "INSERT INTO flashcard_reviews (card_id, quality, reviewed_at) VALUES (?, ?, ?)",
            (card_id, quality, now_iso),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "card_id": card_id,
        "difficulty": difficulty,
        "easiness": round(new_easiness, 2),
        "interval_days": new_interval,
        "next_review": next_review,
    }


def deck_stats(deck_id: str) -> dict:
    """Quick stats for a deck: total, due, learned (interval > 21 days)."""
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE deck_id = ?", (deck_id,)
        ).fetchone()[0]
        due = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE deck_id = ? AND next_review <= ?",
            (deck_id, datetime.now().isoformat()),
        ).fetchone()[0]
        learned = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE deck_id = ? AND interval_days >= 21",
            (deck_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    return {"total": total, "due": due, "learned": learned}
