"""Export/Import: flashcards CSV/Anki, planos JSON, perfil completo.

Permite exportar baralhos em formato CSV compatível com Anki,
planos de estudo em JSON, e importar flashcards de CSV.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import uuid
from datetime import datetime

from ..config import MEMORY_DB_PATH


def _conn():
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Flashcard Export ────────────────────────────────────────────────────────────


def export_deck_csv(deck_id: str) -> str:
    """Export a deck to CSV (Anki-compatible: front TAB back)."""
    conn = _conn()
    try:
        deck = conn.execute(
            "SELECT * FROM flashcard_decks WHERE id = ?", (deck_id,)
        ).fetchone()
        if not deck:
            raise KeyError(f"Baralho {deck_id} não encontrado")
        cards = conn.execute(
            "SELECT front, back FROM flashcards WHERE deck_id = ? ORDER BY created_at",
            (deck_id,),
        ).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    output.write("#separator:tab\n")
    output.write("#html:false\n")
    output.write("#deck:" + dict(deck)["topic"] + "\n")
    for card in cards:
        c = dict(card)
        output.write(f"{c['front']}\t{c['back']}\n")
    return output.getvalue()


def export_deck_json(deck_id: str) -> dict:
    """Export a deck as JSON."""
    conn = _conn()
    try:
        deck = conn.execute(
            "SELECT * FROM flashcard_decks WHERE id = ?", (deck_id,)
        ).fetchone()
        if not deck:
            raise KeyError(f"Baralho {deck_id} não encontrado")
        cards = conn.execute(
            "SELECT front, back, easiness, interval_days, repetitions FROM flashcards "
            "WHERE deck_id = ? ORDER BY created_at",
            (deck_id,),
        ).fetchall()
    finally:
        conn.close()

    deck_dict = dict(deck)
    return {
        "deck": {
            "title": deck_dict["title"],
            "topic": deck_dict["topic"],
            "source_doc": deck_dict["source_doc"],
            "card_count": deck_dict["card_count"],
        },
        "cards": [dict(c) for c in cards],
        "exported_at": datetime.now().isoformat(),
        "format": "studyagent_v1",
    }


# ── Flashcard Import ────────────────────────────────────────────────────────────


def import_deck_csv(file_content: str, topic: str, title: str = "") -> dict:
    """Import flashcards from CSV (tab-separated: front TAB back).

    Accepts Anki-style CSV with header comments (#separator, etc).
    Also supports comma-separated if no tabs found.
    """
    lines = file_content.strip().split("\n")
    data_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        data_lines.append(line)

    if len(data_lines) < 1:
        raise ValueError("CSV vazio ou sem dados válidos")

    # Detect separator
    if "\t" in data_lines[0]:
        sep = "\t"
    else:
        sep = ","

    # Skip header row if it looks like one (first field is non-numeric header)
    start_idx = 0
    if data_lines:
        first_parts = next(csv.reader([data_lines[0]], delimiter=sep))
        if first_parts and first_parts[0].strip().lower() in ("front", "frente", "pergunta", "q", "card"):
            start_idx = 1

    cards = []
    for line in data_lines[start_idx:]:
        parts = next(csv.reader([line], delimiter=sep))
        if len(parts) >= 2:
            front = parts[0].strip()
            back = parts[1].strip()
            if front and back:
                cards.append({"front": front, "back": back})

    if not cards:
        raise ValueError("Nenhum card válido encontrado no CSV")

    return _save_imported_deck(cards, topic, title or topic)


def import_deck_json(file_content: str) -> dict:
    """Import a deck from StudyAgent JSON export."""
    data = json.loads(file_content)
    if data.get("format") != "studyagent_v1":
        raise ValueError("Formato JSON não reconhecido")

    deck_info = data.get("deck", {})
    cards_data = data.get("cards", [])
    topic = deck_info.get("topic", "Importado")

    cards = [{"front": c["front"], "back": c["back"]} for c in cards_data if c.get("front") and c.get("back")]
    if not cards:
        raise ValueError("Nenhum card válido encontrado no JSON")

    return _save_imported_deck(cards, topic, deck_info.get("title", topic))


def _save_imported_deck(cards: list[dict], topic: str, title: str) -> dict:
    """Save imported cards as a new deck."""
    deck_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()

    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    try:
        conn.execute(
            "INSERT INTO flashcard_decks (id, title, topic, source_doc, card_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (deck_id, title, topic, None, len(cards), now),
        )
        for card in cards:
            conn.execute(
                "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
                "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 1, 0, ?, ?)",
                (uuid.uuid4().hex[:8], deck_id, card["front"], card["back"], now, now),
            )
        conn.commit()
    finally:
        conn.close()

    return {"deck_id": deck_id, "topic": topic, "card_count": len(cards)}


# ── Study Plan Export ───────────────────────────────────────────────────────────


def export_plan_json(plan_id: str) -> dict:
    """Export a study plan as JSON."""
    conn = _conn()
    try:
        plan = conn.execute(
            "SELECT * FROM study_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan:
            raise KeyError(f"Plano {plan_id} não encontrado")
        items = conn.execute(
            "SELECT title, detail, done, sort_order FROM study_items "
            "WHERE plan_id = ? ORDER BY sort_order",
            (plan_id,),
        ).fetchall()
    finally:
        conn.close()

    plan_dict = dict(plan)
    return {
        "plan": {
            "title": plan_dict["title"],
            "topic": plan_dict["topic"],
            "total_items": plan_dict["total_items"],
            "done_items": plan_dict["done_items"],
        },
        "items": [dict(it) for it in items],
        "exported_at": datetime.now().isoformat(),
        "format": "studyagent_v1",
    }


# ── Full Profile Export/Import ──────────────────────────────────────────────────


def export_full() -> dict:
    """Export complete study data: profile, mastery, all decks, all plans."""
    conn = _conn()
    try:
        profile = conn.execute("SELECT * FROM student_profile LIMIT 1").fetchone()
        mastery = conn.execute("SELECT * FROM topic_mastery").fetchall()
        decks = conn.execute("SELECT * FROM flashcard_decks").fetchall()
        plans = conn.execute("SELECT * FROM study_plans").fetchall()

        all_cards = []
        for d in decks:
            cards = conn.execute(
                "SELECT front, back, easiness, interval_days, repetitions FROM flashcards WHERE deck_id = ?",
                (dict(d)["id"],),
            ).fetchall()
            all_cards.append({
                "deck": dict(d),
                "cards": [dict(c) for c in cards],
            })

        all_items = []
        for p in plans:
            items = conn.execute(
                "SELECT title, detail, done, sort_order FROM study_items WHERE plan_id = ?",
                (dict(p)["id"],),
            ).fetchall()
            all_items.append({
                "plan": dict(p),
                "items": [dict(it) for it in items],
            })
    finally:
        conn.close()

    return {
        "profile": dict(profile) if profile else None,
        "mastery": [dict(m) for m in mastery],
        "decks": all_cards,
        "plans": all_items,
        "exported_at": datetime.now().isoformat(),
        "format": "studyagent_full_v1",
    }


def import_full(data: dict) -> dict:
    """Import complete study data (overwrite profile, append decks/plans)."""
    if data.get("format") != "studyagent_full_v1":
        raise ValueError("Formato não reconhecido")

    imported = {"profile": False, "mastery": 0, "decks": 0, "plans": 0}
    now = datetime.now().isoformat()

    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    try:
        # Profile
        profile = data.get("profile")
        if profile:
            existing = conn.execute("SELECT id FROM student_profile LIMIT 1").fetchone()
            if existing:
                conn.execute(
                    "UPDATE student_profile SET name=?, grade=?, school=?, preferences=?, updated_at=? WHERE id=?",
                    (profile.get("name", ""), profile.get("grade", ""), profile.get("school", ""),
                     profile.get("preferences", ""), now, existing[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO student_profile (id, name, grade, school, preferences, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("student1", profile.get("name", ""), profile.get("grade", ""),
                     profile.get("school", ""), profile.get("preferences", ""), now, now),
                )
            imported["profile"] = True

        # Mastery
        for m in data.get("mastery", []):
            conn.execute(
                "INSERT OR REPLACE INTO topic_mastery "
                "(topic, attempts, correct, total_questions, avg_percent, last_practiced, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (m["topic"], m.get("attempts", 0), m.get("correct", 0),
                 m.get("total_questions", 0), m.get("avg_percent", 0),
                 m.get("last_practiced"), m.get("created_at", now), now),
            )
            imported["mastery"] += 1

        # Decks
        for d in data.get("decks", []):
            deck_info = d.get("deck", {})
            cards = d.get("cards", [])
            deck_id = uuid.uuid4().hex[:10]
            conn.execute(
                "INSERT INTO flashcard_decks (id, title, topic, source_doc, card_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (deck_id, deck_info.get("title", ""), deck_info.get("topic", ""),
                 deck_info.get("source_doc"), len(cards), now),
            )
            for card in cards:
                conn.execute(
                    "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
                    "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                    (uuid.uuid4().hex[:8], deck_id, card["front"], card["back"],
                     card.get("easiness", 2.5), card.get("interval_days", 1), now, now),
                )
            imported["decks"] += 1

        # Plans
        for pl in data.get("plans", []):
            plan_info = pl.get("plan", {})
            items = pl.get("items", [])
            plan_id = uuid.uuid4().hex[:10]
            conn.execute(
                "INSERT INTO study_plans (id, title, topic, total_items, done_items, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (plan_id, plan_info.get("title", ""), plan_info.get("topic", ""),
                 plan_info.get("total_items", len(items)), plan_info.get("done_items", 0), now),
            )
            for i, item in enumerate(items):
                conn.execute(
                    "INSERT INTO study_items (plan_id, title, detail, done, sort_order) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (plan_id, item.get("title", ""), item.get("detail", ""),
                     item.get("done", 0), item.get("sort_order", i)),
                )
            imported["plans"] += 1

        conn.commit()
    finally:
        conn.close()

    return imported
