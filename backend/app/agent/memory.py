"""Memória de longo prazo do agente — SQLite com 16 tabelas.

Gerencia sessões, mensagens, resumos, documentos, e todas as tabelas
do tutor (exercícios, flashcards, planos, perfil, gamificação).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from ..config import MEMORY_DB_PATH
from ..db import get_connection


class Memory:
    def __init__(self, db_path=MEMORY_DB_PATH):
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = get_connection(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                session_id TEXT PRIMARY KEY REFERENCES sessions(id),
                summary TEXT NOT NULL,
                msg_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                pages INTEGER NOT NULL DEFAULT 0,
                chars INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exercise_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_id TEXT NOT NULL,
                topic       TEXT NOT NULL,
                score       INTEGER NOT NULL,
                total       INTEGER NOT NULL,
                percent     INTEGER NOT NULL,
                level       TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS flashcard_decks (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                topic       TEXT,
                source_doc  TEXT,
                card_count  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS flashcards (
                id             TEXT PRIMARY KEY,
                deck_id        TEXT NOT NULL REFERENCES flashcard_decks(id),
                front          TEXT NOT NULL,
                back           TEXT NOT NULL,
                easiness       REAL NOT NULL DEFAULT 2.5,
                interval_days  INTEGER NOT NULL DEFAULT 1,
                repetitions    INTEGER NOT NULL DEFAULT 0,
                next_review    TEXT NOT NULL,
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS flashcard_reviews (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id    TEXT NOT NULL REFERENCES flashcards(id),
                quality    INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS study_plans (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                topic       TEXT NOT NULL,
                total_items INTEGER NOT NULL DEFAULT 0,
                done_items  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS study_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id    TEXT NOT NULL REFERENCES study_plans(id),
                title      TEXT NOT NULL,
                detail     TEXT,
                done       INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS student_profile (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                grade       TEXT NOT NULL DEFAULT '',
                school      TEXT NOT NULL DEFAULT '',
                preferences TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topic_mastery (
                topic           TEXT PRIMARY KEY,
                attempts        INTEGER NOT NULL DEFAULT 0,
                correct         INTEGER NOT NULL DEFAULT 0,
                total_questions INTEGER NOT NULL DEFAULT 0,
                avg_percent     INTEGER NOT NULL DEFAULT 0,
                weighted_score  REAL NOT NULL DEFAULT 0.0,
                last_practiced  TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topic_results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT NOT NULL,
                percent         INTEGER NOT NULL,
                difficulty_level TEXT NOT NULL DEFAULT 'médio',
                created_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_topic_results_topic
                ON topic_results(topic, created_at DESC);

            CREATE TABLE IF NOT EXISTS action_proposals (
                id               TEXT PRIMARY KEY,
                action_type      TEXT NOT NULL,
                params           TEXT NOT NULL DEFAULT '{}',
                description      TEXT NOT NULL DEFAULT '',
                status           TEXT NOT NULL DEFAULT 'pending',
                rejection_reason TEXT NOT NULL DEFAULT '',
                created_at       TEXT NOT NULL,
                resolved_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS session_log (
                id               TEXT PRIMARY KEY,
                session_type     TEXT NOT NULL,
                started_at       TEXT NOT NULL,
                ended_at         TEXT,
                duration_seconds INTEGER,
                metadata         TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS adaptive_difficulty (
                topic        TEXT PRIMARY KEY,
                current_level TEXT NOT NULL DEFAULT 'médio',
                window_avg   REAL NOT NULL DEFAULT 50.0,
                window_count INTEGER NOT NULL DEFAULT 0,
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id             TEXT PRIMARY KEY,
                achievement_id TEXT NOT NULL,
                earned_at      TEXT NOT NULL,
                metadata       TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS error_notebook (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT NOT NULL,
                question        TEXT NOT NULL,
                user_answer     TEXT NOT NULL,
                correct_answer  TEXT NOT NULL,
                explanation     TEXT NOT NULL DEFAULT '',
                exercise_id     TEXT NOT NULL DEFAULT '',
                reviewed        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_error_notebook_topic
                ON error_notebook(topic, reviewed, created_at DESC);

            CREATE TABLE IF NOT EXISTS student_xp (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                amount      INTEGER NOT NULL,
                source      TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS student_level (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                level      TEXT NOT NULL DEFAULT 'Iniciante',
                total_xp   INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    def add_document(self, name, path, pages, chars):
        doc_id = str(uuid.uuid4())[:8]
        conn = get_connection(self._db_path)
        conn.execute(
            "INSERT INTO documents (id, name, path, pages, chars, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, name, str(path), pages, chars, datetime.now().isoformat()),
        )
        conn.commit()
        return doc_id

    def get_document(self, doc_id):
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def list_documents(self):
        conn = get_connection(self._db_path)
        rows = conn.execute(
            "SELECT id, name, pages, chars, created_at FROM documents ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_summary(self, session_id):
        conn = get_connection(self._db_path)
        row = conn.execute(
            "SELECT summary, msg_count FROM summaries WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def set_summary(self, session_id, summary, msg_count):
        conn = get_connection(self._db_path)
        conn.execute(
            """
            INSERT INTO summaries (session_id, summary, msg_count, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                summary = excluded.summary,
                msg_count = excluded.msg_count,
                updated_at = excluded.updated_at
            """,
            (session_id, summary, msg_count, datetime.now().isoformat()),
        )
        conn.commit()

    def count_messages(self, session_id):
        conn = get_connection(self._db_path)
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row["n"]

    def new_session(self, title=None):
        session_id = str(uuid.uuid4())[:8]
        conn = get_connection(self._db_path)
        conn.execute(
            "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
            (session_id, title, datetime.now().isoformat()),
        )
        conn.commit()
        return session_id

    def session_exists(self, session_id):
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def get_or_create_session(self, session_id=None):
        if session_id and self.session_exists(session_id):
            return session_id
        return self.new_session()

    def add_message(self, session_id, role, content):
        conn = get_connection(self._db_path)
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        conn.commit()

    def history(self, session_id, limit=20):
        conn = get_connection(self._db_path)
        rows = conn.execute(
            """
            SELECT role, content FROM (
                SELECT * FROM messages WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def history_head(self, session_id, count):
        conn = get_connection(self._db_path)
        rows = conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ? ORDER BY id ASC LIMIT ?
            """,
            (session_id, count),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def list_sessions(self):
        conn = get_connection(self._db_path)
        rows = conn.execute(
            "SELECT s.id, s.title, s.created_at, COUNT(m.id) AS message_count "
            "FROM sessions s LEFT JOIN messages m ON m.session_id = s.id "
            "GROUP BY s.id ORDER BY s.created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
