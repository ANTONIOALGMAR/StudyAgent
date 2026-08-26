"""Gerador de exercícios com correção automática.

Fluxo:
1. O LLM gera questões em JSON estrito (enunciado, alternativas opcionais,
   gabarito e explicação).
2. O gabarito fica guardado no servidor — o frontend nunca recebe a resposta.
3. Na correção, comparação normalizada; se divergir, o LLM decide equivalência.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import uuid

from ..agent.llm import chat
from ..db import get_connection

QUESTION_LIMIT = 8
MAX_STORED = 20

_GEN_PROMPT = (
    "Você é um criador de exercícios escolares brasileiros.\n"
    "Gere {n} questões sobre: {topic}.\n"
    "Nível: {level}. Misture dificuldades fáceis, médias e uma difícil.\n"
    "{style_hint}\n"
    "Cada questão deve ter resposta curta e objetiva.\n\n"
    'Responda ESTRITAMENTE neste JSON, sem nenhum texto fora dele:\n'
    '{{"questions": [{{"q": "enunciado", "options": ["a) ...","b) ...","c) ...","d) ..."] '
    'ou null para resposta aberta, "answer": "gabarito curto", "explanation": "explicação em 1-2 frases"}}]}}'
)

_EQUIV_PROMPT = (
    "Duas respostas de exercício são equivalentes?\n"
    'Resposta 1: "{a}"\n'
    'Resposta 2: "{b}"\n'
    'Considere forma diferente mas mesmo significado/valor como equivalentes.\n'
    'Responda apenas SIM ou NÃO.'
)


def _init_exercises_table():
    conn = get_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS exercise_store (
            exercise_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            items_json TEXT NOT NULL,
            created_at REAL NOT NULL
        )"""
    )
    conn.commit()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = re.sub(r"^[a-d]\)\s*", "", value)
    value = re.sub(r"[^\w\s/.,]", "", value)
    value = value.replace(",", ".")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .")


def _prune() -> None:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM exercise_store").fetchone()[0]
    if count > MAX_STORED:
        conn.execute(
            "DELETE FROM exercise_store WHERE exercise_id IN "
            "(SELECT exercise_id FROM exercise_store ORDER BY created_at ASC LIMIT ?)",
            (count - MAX_STORED,),
        )
        conn.commit()


def generate(topic: str, n: int = 4, level: str = "ensino fundamental") -> dict:
    _init_exercises_table()
    n = max(1, min(n, QUESTION_LIMIT))
    style_hint = (
        "Use múltipla escolha com 4 alternativas."
        if level != "aberta"
        else "Todas as questões devem ser de resposta aberta (options: null)."
    )
    prompt = _GEN_PROMPT.format(n=n, topic=topic, level=level, style_hint=style_hint)
    raw = chat([{"role": "user", "content": prompt}])
    data = json.loads(_strip_fences(raw))
    questions = data.get("questions") or []
    cleaned = []
    for q in questions[:n]:
        if not isinstance(q, dict) or not q.get("q") or not q.get("answer"):
            continue
        opts = q.get("options")
        cleaned.append({
            "id": uuid.uuid4().hex[:8],
            "q": str(q["q"]),
            "options": [str(o) for o in opts] if isinstance(opts, list) and opts else None,
            "answer": str(q["answer"]),
            "explanation": str(q.get("explanation") or ""),
        })
    if not cleaned:
        raise ValueError("O modelo não conseguiu gerar questões válidas. Tente outro tema.")

    exercise_id = uuid.uuid4().hex[:10]
    conn = get_connection()
    conn.execute(
        "INSERT INTO exercise_store (exercise_id, topic, items_json, created_at) VALUES (?, ?, ?, ?)",
        (exercise_id, topic, json.dumps(cleaned, ensure_ascii=False), time.time()),
    )
    conn.commit()
    _prune()

    public = [{"id": q["id"], "q": q["q"], "options": q["options"]} for q in cleaned]
    return {"exercise_id": exercise_id, "topic": topic, "questions": public}


def _equivalent(user: str, expected: str) -> bool:
    try:
        out = chat([{"role": "user", "content": _EQUIV_PROMPT.format(a=user, b=expected)}])
        return out.strip().lower().startswith("sim")
    except Exception:
        return False


def grade(exercise_id: str, answers: dict[str, str]) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT items_json FROM exercise_store WHERE exercise_id = ?", (exercise_id,)
    ).fetchone()
    if not row:
        raise KeyError("Exercício expirado ou inexistente. Gere um novo.")
    items = json.loads(row["items_json"])

    results = []
    score = 0
    for q in items:
        user_raw = (answers.get(q["id"]) or "").strip()
        expected = q["answer"]
        correct = bool(user_raw)
        if correct:
            if _normalize(user_raw) == _normalize(expected):
                pass
            elif q["options"] is None and _equivalent(user_raw, expected):
                pass
            else:
                correct = False
        score += correct
        results.append({
            "id": q["id"],
            "q": q["q"],
            "user_answer": user_raw,
            "expected": expected,
            "correct": correct,
            "explanation": q["explanation"],
        })

    total = len(results)
    pct = round(100 * score / max(total, 1))
    if pct >= 80:
        message = f"Excelente! Você acertou {score} de {total}. Está pronto pra prova! 🎉"
    elif pct >= 50:
        message = f"Bom trabalho: {score} de {total}. Revise as erradas e tente de novo!"
    else:
        message = f"{score} de {total}. Sem problema — vamos estudar esse tema juntos!"

    return {
        "exercise_id": exercise_id,
        "score": score,
        "total": total,
        "percent": pct,
        "message": message,
        "results": results,
    }


def grade_and_track(exercise_id: str, answers: dict[str, str]) -> dict:
    from ..tutor.error_notebook import log_errors_from_exercise
    from ..tutor.profile import update_from_exercise
    from ..tutor.stats import save_exercise_result

    conn = get_connection()
    row = conn.execute(
        "SELECT topic FROM exercise_store WHERE exercise_id = ?", (exercise_id,)
    ).fetchone()
    result = grade(exercise_id, answers)
    if row:
        topic = row["topic"]
        try:
            update_from_exercise(topic, result["score"], result["total"], result["percent"])
            save_exercise_result(exercise_id, topic, result["score"], result["total"], result["percent"])
            log_errors_from_exercise(exercise_id, topic, result.get("results", []))
            from ..tutor.gamification import award_exercise_xp
            xp_result = award_exercise_xp(result["score"], result["total"], "médio")
            result["xp"] = xp_result
        except Exception:
            pass
    return result
