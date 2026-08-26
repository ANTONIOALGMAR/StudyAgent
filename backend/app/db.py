"""Conexão SQLite centralizada com WAL mode e pool simples.

Substitui os _conn() duplicados em cada módulo tutor.
Usa check_same_thread=False para FastAPI (async → threads).
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import MEMORY_DB_PATH

_local = threading.local()


def get_connection(db_path: Path | str = MEMORY_DB_PATH) -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode and Row factory.

    Returns the same connection within the same thread, creating one if needed.
    """
    key = str(db_path)
    conns = getattr(_local, "conns", None)
    if conns is None:
        conns = {}
        _local.conns = conns

    if key not in conns:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conns[key] = conn

    return conns[key]


def close_all() -> None:
    """Close all thread-local connections (for cleanup)."""
    conns = getattr(_local, "conns", None)
    if conns:
        for conn in conns.values():
            try:
                conn.close()
            except Exception:
                pass
        conns.clear()


@contextmanager
def db_cursor(db_path: Path | str = MEMORY_DB_PATH):
    """Context manager yielding a cursor with auto-commit on success."""
    conn = get_connection(db_path)
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
