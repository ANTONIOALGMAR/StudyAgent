import sqlite3
import threading
import uuid
from datetime import datetime

from ..config import MEMORY_DB_PATH


class Memory:
    def __init__(self, db_path=MEMORY_DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock, self._connect() as conn:
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

    def new_session(self, title=None):
        session_id = str(uuid.uuid4())[:8]
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
                (session_id, title, datetime.now().isoformat()),
            )
        return session_id

    def session_exists(self, session_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return row is not None

    def get_or_create_session(self, session_id=None):
        if session_id and self.session_exists(session_id):
            return session_id
        return self.new_session()

    def add_message(self, session_id, role, content):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, datetime.now().isoformat()),
            )

    def history(self, session_id, limit=20):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT * FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def list_sessions(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT s.id, s.title, s.created_at, COUNT(m.id) AS message_count "
                "FROM sessions s LEFT JOIN messages m ON m.session_id = s.id "
                "GROUP BY s.id ORDER BY s.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
