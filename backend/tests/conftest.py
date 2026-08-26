import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_ALL_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, title TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
    role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS summaries (
    session_id TEXT PRIMARY KEY, summary TEXT NOT NULL,
    msg_count INTEGER DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL,
    pages INTEGER DEFAULT 0, chars INTEGER DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exercise_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_id TEXT NOT NULL,
    topic TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL,
    percent INTEGER NOT NULL, level TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exercise_store (
    exercise_id TEXT PRIMARY KEY, topic TEXT NOT NULL,
    items_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS flashcard_decks (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, topic TEXT,
    source_doc TEXT, card_count INTEGER DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY, deck_id TEXT NOT NULL, front TEXT NOT NULL,
    back TEXT NOT NULL, easiness REAL DEFAULT 2.5, interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0, next_review TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS flashcard_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT NOT NULL,
    quality INTEGER NOT NULL, reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_plans (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, topic TEXT NOT NULL,
    total_items INTEGER DEFAULT 0, done_items INTEGER DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT NOT NULL,
    title TEXT NOT NULL, detail TEXT, done INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS student_profile (
    id TEXT PRIMARY KEY, name TEXT DEFAULT '', grade TEXT DEFAULT '',
    school TEXT DEFAULT '', preferences TEXT DEFAULT '',
    created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS topic_mastery (
    topic TEXT PRIMARY KEY, attempts INTEGER DEFAULT 0,
    correct INTEGER DEFAULT 0, total_questions INTEGER DEFAULT 0,
    avg_percent INTEGER DEFAULT 0, weighted_score REAL DEFAULT 0.0,
    last_practiced TEXT,
    created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS topic_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL,
    percent INTEGER NOT NULL, difficulty_level TEXT DEFAULT 'médio',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS action_proposals (
    id TEXT PRIMARY KEY, action_type TEXT NOT NULL,
    params TEXT DEFAULT '{}', description TEXT DEFAULT '',
    status TEXT DEFAULT 'pending', rejection_reason TEXT DEFAULT '',
    created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS session_log (
    id TEXT PRIMARY KEY, session_type TEXT NOT NULL, started_at TEXT NOT NULL,
    ended_at TEXT, duration_seconds INTEGER, metadata TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS adaptive_difficulty (
    topic TEXT PRIMARY KEY, current_level TEXT DEFAULT 'médio',
    window_avg REAL DEFAULT 50.0, window_count INTEGER DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY, achievement_id TEXT NOT NULL,
    earned_at TEXT NOT NULL, metadata TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS error_notebook (
    id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL,
    question TEXT NOT NULL, user_answer TEXT NOT NULL,
    correct_answer TEXT NOT NULL, explanation TEXT DEFAULT '',
    exercise_id TEXT DEFAULT '', reviewed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS student_xp (
    id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER NOT NULL,
    source TEXT NOT NULL, description TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS student_level (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    level TEXT NOT NULL DEFAULT 'Iniciante',
    total_xp INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""

_MODULES_USING_DB = [
    "app.tutor.profile",
    "app.tutor.flashcards",
    "app.tutor.advanced_profile",
    "app.tutor.gamification",
    "app.tutor.export_import",
    "app.tutor.automation",
    "app.tutor.stats",
    "app.tutor.study_plan",
    "app.tutor.error_notebook",
    "app.agent.exercises",
    "app.agent.memory",
]


@pytest.fixture
def tmp_db(tmp_path):
    """Create a fresh temp DB and patch get_connection in all modules."""
    from app.db import _local

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_ALL_TABLES)
    conn.row_factory = sqlite3.Row
    conn.commit()
    conn.close()

    # Clear cached connections from previous tests
    _local.conns = {}

    def _make_conn(db_path_arg=None):
        c = sqlite3.connect(str(db_path), check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    patches = [patch(f"{mod}.get_connection", side_effect=_make_conn) for mod in _MODULES_USING_DB]
    for p in patches:
        p.start()
    yield db_path
    for p in patches:
        p.stop()
    _local.conns = {}
