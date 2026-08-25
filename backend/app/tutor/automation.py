"""Automação com confirmação: proposta de ação do agente.

Quando o agente quer executar uma ação (gerar exercícios, criar plano,
pesquisar), emite uma proposta JSON. O frontend exibe um diálogo de
confirmação. O usuário aprova → ação executada; rejeita → agente explica.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime

from ..config import MEMORY_DB_PATH

ACTION_TYPES = (
    "generate_exercises",
    "generate_flashcards",
    "generate_study_plan",
    "web_search",
    "open_url",
)

ACTION_LABELS = {
    "generate_exercises": "Gerar exercícios",
    "generate_flashcards": "Gerar flashcards",
    "generate_study_plan": "Criar plano de estudo",
    "web_search": "Pesquisar na web",
    "open_url": "Abrir página",
}


def _conn():
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def create_proposal(action_type: str, params: dict, description: str = "") -> dict:
    """Create a pending action proposal."""
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Tipo de ação desconhecido: {action_type}")
    proposal_id = uuid.uuid4().hex[:10]
    now = datetime.now().isoformat()
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO action_proposals (id, action_type, params, description, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (proposal_id, action_type, json.dumps(params, ensure_ascii=False), description, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "proposal_id": proposal_id,
        "action_type": action_type,
        "label": ACTION_LABELS.get(action_type, action_type),
        "description": description,
        "params": params,
        "status": "pending",
    }


def approve(proposal_id: str) -> dict:
    """Approve and return the proposal details for execution."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM action_proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Proposta {proposal_id} não encontrada")
        proposal = dict(row)
        if proposal["status"] != "pending":
            return {"status": proposal["status"], "message": "Proposta já processada"}
        conn.execute(
            "UPDATE action_proposals SET status = 'approved', resolved_at = ? WHERE id = ?",
            (datetime.now().isoformat(), proposal_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "status": "approved",
        "proposal_id": proposal_id,
        "action_type": proposal["action_type"],
        "params": json.loads(proposal["params"]),
    }


def reject(proposal_id: str, reason: str = "") -> dict:
    """Reject a proposal."""
    conn = _conn()
    try:
        conn.execute(
            "UPDATE action_proposals SET status = 'rejected', resolved_at = ?, rejection_reason = ? WHERE id = ?",
            (datetime.now().isoformat(), reason, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "rejected", "proposal_id": proposal_id, "reason": reason}


def get_pending() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM action_proposals WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        r = dict(r)
        r["params"] = json.loads(r["params"])
        r["label"] = ACTION_LABELS.get(r["action_type"], r["action_type"])
        result.append(r)
    return result


def list_recent(limit: int = 10) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM action_proposals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        r = dict(r)
        r["params"] = json.loads(r["params"])
        r["label"] = ACTION_LABELS.get(r["action_type"], r["action_type"])
        result.append(r)
    return result


def inject_proposal_prompt() -> str:
    """System prompt addition that teaches the agent to emit proposals."""
    return (
        "\n\nQuando quiser executar uma ação (gerar exercícios, criar plano de estudo, "
        "gerar flashcards ou pesquisar), emita UMA ÚNICA vez um bloco JSON no início "
        "da resposta, entre ````json` e ````:\n"
        '{"action": {"type": "TIPO", "params": {...}, "description": "descrição curta"}}\n'
        "Tipos válidos: generate_exercises, generate_flashcards, generate_study_plan, web_search, open_url.\n"
        "Depois do bloco, escreva uma mensagem curta ao aluno confirmando o que vai fazer.\n"
        "NÃO emita o bloco se o aluno apenas estiver perguntando ou conversando."
    )
