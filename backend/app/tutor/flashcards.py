"""Flashcards com repetição espaçada SM-2 e geração via LLM.

Algoritmo SM-2 adaptado de Piotr Wozniak (25 Anki).
Armazenamento em SQLite via tabela flashcards + flashcard_reviews.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta

from ..agent.llm import chat
from ..db import get_connection

DEFAULT_EASINESS = 2.5
MIN_EASINESS = 1.3
INITIAL_INTERVAL_DAYS = 1


def sm2_next(easiness: float, interval: int, repetitions: int, quality: int) -> tuple[float, int, int]:
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
    mapping = {"again": 1, "hard": 2, "good": 3, "easy": 5}
    return mapping.get(difficulty, 3)


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
        cards.append({
            "id": uuid.uuid4().hex[:8],
            "front": str(c["front"]),
            "back": str(c["back"]),
        })

    if not cards:
        raise ValueError("O modelo não gerou flashcards válidos. Tente outro tema.")

    conn = get_connection()
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

    return {"deck_id": deck_id, "topic": topic, "card_count": len(cards), "cards": cards}


def due_cards(deck_id: str, limit: int = 20) -> list[dict]:
    now = datetime.now().isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM flashcards WHERE deck_id = ? AND next_review <= ? "
        "ORDER BY next_review ASC LIMIT ?",
        (deck_id, now, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_decks() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM flashcard_decks ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def review_card(card_id: str, difficulty: str) -> dict:
    quality = quality_from_difficulty(difficulty)
    now = datetime.now()
    now_iso = now.isoformat()

    conn = get_connection()
    row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        raise KeyError(f"Flashcard {card_id} não encontrado")
    card = dict(row)
    new_easiness, new_interval, new_reps = sm2_next(
        card["easiness"], card["interval_days"], card["repetitions"], quality
    )
    next_review = (now + timedelta(days=new_interval)).isoformat()
    conn.execute(
        "UPDATE flashcards SET easiness=?, interval_days=?, repetitions=?, next_review=? WHERE id=?",
        (new_easiness, new_interval, new_reps, next_review, card_id),
    )
    conn.execute(
        "INSERT INTO flashcard_reviews (card_id, quality, reviewed_at) VALUES (?, ?, ?)",
        (card_id, quality, now_iso),
    )
    conn.commit()
    _track_flashcard_topic(card["deck_id"], quality)
    from .gamification import award_flashcard_xp
    award_flashcard_xp(quality >= 3)

    return {
        "card_id": card_id,
        "difficulty": difficulty,
        "easiness": round(new_easiness, 2),
        "interval_days": new_interval,
        "next_review": next_review,
    }


def _track_flashcard_topic(deck_id: str, quality: int) -> None:
    try:
        from .profile import update_from_flashcard_review
        conn = get_connection()
        row = conn.execute(
            "SELECT topic FROM flashcard_decks WHERE id = ?", (deck_id,)
        ).fetchone()
        if row and row["topic"]:
            update_from_flashcard_review(row["topic"], quality)
    except Exception:
        pass


def deck_stats(deck_id: str) -> dict:
    conn = get_connection()
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
    return {"total": total, "due": due, "learned": learned}


def generate_from_errors(
    topic: str | None = None,
    limit: int = 10,
) -> dict:
    """Generate flashcards from error notebook entries.

    Creates a deck from wrong answers, using the question as front
    and the correct answer + explanation as back.
    """
    from .error_notebook import errors_for_flashcards, mark_topic_reviewed

    errors = errors_for_flashcards(topic=topic)
    if not errors:
        return {"deck_id": None, "card_count": 0, "message": "Nenhum erro pendente para gerar flashcards."}

    deck_title = "Revisão de erros" + (f" — {topic}" if topic else "")
    deck_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()
    cards = []

    for err in errors[:limit]:
        front = f"Questão: {err['question']}"
        back = f"Resposta correta: {err['correct_answer']}"
        if err.get("explanation"):
            back += f"\nExplicação: {err['explanation']}"
        cards.append({
            "id": uuid.uuid4().hex[:8],
            "front": front,
            "back": back,
        })

    conn = get_connection()
    conn.execute(
        "INSERT INTO flashcard_decks (id, title, topic, source_doc, card_count, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (deck_id, deck_title, topic or "geral", None, len(cards), now),
    )
    for card in cards:
        conn.execute(
            "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
            "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 1, 0, ?, ?)",
            (card["id"], deck_id, card["front"], card["back"], now, now),
        )
    conn.commit()

    # Mark errors as reviewed
    if topic:
        mark_topic_reviewed(topic)

    return {
        "deck_id": deck_id,
        "topic": topic or "geral",
        "card_count": len(cards),
        "cards": cards,
        "source": "error_notebook",
    }
