"""Teste de integração com banco SQLite real (aplicação de produção, sem mock).

Cobre o R20 do risk-register: o restante da suíte usa `get_connection` mockado
em 11 módulos (conftest.py); aqui exercitamos o caminho real de produção em
`app.db.get_connection(db_path)` — pool thread-local, WAL, foreign_keys e
persistência entre conexões — contra um arquivo temporário real.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
    role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


@pytest.fixture
def real_db(tmp_path):
    path = tmp_path / "real.db"
    conn = get_connection(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    yield path, conn
    conn.close()


def test_conn_reutilizada_no_mesmo_thread(real_db):
    path, conn = real_db
    # Mesmo caminho dentro do mesmo thread devolve a mesma conexão (pool local).
    assert get_connection(path) is conn


def test_wal_mode_ativado(real_db):
    _, conn = real_db
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_foreign_keys_ativado(real_db):
    _, conn = real_db
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_scritura_persiste_entre_conexoes(real_db):
    path, conn = real_db
    conn.execute(
        "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
        ("s1", "Aula de matemática", "2026-09-01T00:00:00"),
    )
    conn.commit()

    # Nova conexão lê o que foi gravado (persistência real em disco).
    conn2 = get_connection(path)
    row = conn2.execute("SELECT * FROM sessions WHERE id = ?", ("s1",)).fetchone()
    assert row is not None
    assert row["title"] == "Aula de matemática"


def test_row_factory_retorna_sqlite3_row(real_db):
    _, conn = real_db
    conn.execute(
        "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
        ("s2", "x", "2026-09-01T00:00:00"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", ("s2",)).fetchone()
    assert type(row) is sqlite3.Row


def test_transacao_rollback_nao_persiste(tmp_path):
    path = tmp_path / "rollback.db"
    get_connection(path).executescript(_SCHEMA)
    conn = get_connection(path)
    conn.execute("INSERT INTO sessions (id, title, created_at) VALUES (?,?,?)", ("r", "t", "c"))
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
