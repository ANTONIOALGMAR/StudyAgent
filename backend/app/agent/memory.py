"""Memória de longo prazo do agente — SQLite com 16 tabelas.

Gerencia sessões, mensagens, resumos, documentos, e todas as tabelas
do tutor (exercícios, flashcards, planos, perfil, gamificação).
"""

from __future__ import annotations

import re
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
        self._ensure_environment_object_columns(conn)
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
            CREATE TABLE IF NOT EXISTS environment_objects (
                id          TEXT PRIMARY KEY,
                object_name TEXT NOT NULL,
                location    TEXT NOT NULL,
                room        TEXT NOT NULL DEFAULT '',
                area        TEXT NOT NULL DEFAULT '',
                context     TEXT NOT NULL DEFAULT '',
                confidence  REAL NOT NULL DEFAULT 1.0,
                last_seen_at TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_environment_objects_name
                ON environment_objects(object_name, last_seen_at DESC);

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

    def _ensure_environment_object_columns(self, conn):
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='environment_objects'"
        ).fetchone()
        if not table_exists:
            return
        columns = {row[1] for row in conn.execute("PRAGMA table_info(environment_objects)").fetchall()}
        for name, ddl in {
            "room": "TEXT NOT NULL DEFAULT ''",
            "area": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE environment_objects ADD COLUMN {name} {ddl}")

    @staticmethod
    def _normalize_object_name(name: str) -> str:
        text = re.sub(r"\s+", " ", (name or "").strip().lower())
        text = text.replace("meu ", "").replace("minha ", "").replace("o ", "").replace("a ", "")
        return text.strip()

    @staticmethod
    def _normalize_place_name(name: str) -> str:
        text = re.sub(r"\s+", " ", (name or "").strip().lower())
        text = re.sub(r"^(?:no|na|em|do|da|dos|das|sobre|cima|embaixo|dentro|fora)\s+", "", text)
        return text.strip()

    def remember_object_location(
        self,
        object_name: str,
        location: str,
        context: str = "",
        confidence: float = 1.0,
        room: str | None = None,
        area: str | None = None,
    ):
        object_key = self._normalize_object_name(object_name)
        if not object_key or not location or not location.strip():
            return None
        cleaned_location = re.sub(r"\s+", " ", location.strip())
        cleaned_room = self._normalize_place_name(room) if room else ""
        cleaned_area = self._normalize_place_name(area) if area else ""
        now = datetime.now().isoformat()
        conn = get_connection(self._db_path)
        existing = conn.execute(
            "SELECT id, confidence FROM environment_objects WHERE object_name = ? ORDER BY updated_at DESC LIMIT 1",
            (object_key,),
        ).fetchone()
        if existing:
            merged_confidence = max(float(confidence), float(existing["confidence"]))
            conn.execute(
                "UPDATE environment_objects SET location=?, room=?, area=?, context=?, confidence=?, last_seen_at=?, updated_at=? WHERE id=?",
                (cleaned_location, cleaned_room, cleaned_area, (context or "").strip(), merged_confidence, now, now, existing["id"]),
            )
            record = dict(existing)
            record.update({
                "object_name": object_key,
                "location": cleaned_location,
                "room": cleaned_room,
                "area": cleaned_area,
                "context": (context or "").strip(),
                "confidence": merged_confidence,
                "last_seen_at": now,
                "updated_at": now,
            })
            conn.commit()
            return record
        obj_id = str(uuid.uuid4())[:12]
        conn.execute(
            "INSERT INTO environment_objects (id, object_name, location, room, area, context, confidence, last_seen_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (obj_id, object_key, cleaned_location, cleaned_room, cleaned_area, (context or "").strip(), float(confidence), now, now, now),
        )
        conn.commit()
        return {
            "id": obj_id,
            "object_name": object_key,
            "location": cleaned_location,
            "room": cleaned_room,
            "area": cleaned_area,
            "context": (context or "").strip(),
            "confidence": float(confidence),
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
        }

    def remember_visual_detection(self, object_name: str, bbox: dict | None, monitor: int | None = None, context: str = "", confidence: float = 0.9, room: str | None = None, area: str | None = None):
        """
        Registra uma detecção visual estruturada (label + bbox) na memória.

        Mantido por compatibilidade; delega para reconcile_detection com política
        padrão (delta_threshold=0.15).
        """
        return self.reconcile_detection(object_name, bbox, monitor=monitor, context=context, confidence=confidence, room=room, area=area)

    def _notify_frontend(self, title: str, body: str) -> None:
        """
        Tenta inserir uma notificação em `inbox_entries`. Se a tabela não
        existir, cria-a com um esquema simples e insere a linha.
        """
        conn = get_connection(self._db_path)
        now = datetime.now().isoformat()
        try:
            conn.execute(
                "INSERT INTO inbox_entries (id, title, body, created_at, read) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), title, body, now, 0),
            )
            conn.commit()
        except Exception:
            # tenta criar tabela e inserir novamente
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS inbox_entries (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0)"
                )
                conn.execute(
                    "INSERT INTO inbox_entries (id, title, body, created_at, read) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), title, body, now, 0),
                )
                conn.commit()
            except Exception:
                # best-effort: don't crash the agent
                return

    def reconcile_detection(self, object_name: str, bbox: dict | None, monitor: int | None = None, context: str = "", confidence: float = 0.9, room: str | None = None, area: str | None = None, delta_threshold: float = 0.15):
        """
        Reconciliar uma detecção estruturada com a memória existente.

        Regras:
        - Se não há registro existente: criar novo (via remember_object_location).
        - Se há registro, comparar confidências:
          * Se det_conf >= existing_conf + delta_threshold: atualizar para novo local.
          * Se det_conf <= existing_conf - delta_threshold and both >= 0.8: marcar contradição, reduzir confiança existente levemente e notificar o frontend.
          * Caso contrário: merge — atualizar last_seen_at e elevar confiança para max(existing, det).
        """
        if not object_name:
            return None
        obj_key = self._normalize_object_name(object_name)
        if not obj_key:
            return None
        conn = get_connection(self._db_path)
        existing = conn.execute(
            "SELECT * FROM environment_objects WHERE object_name = ? ORDER BY updated_at DESC LIMIT 1",
            (obj_key,),
        ).fetchone()
        # monta location a partir do bbox
        try:
            if bbox and isinstance(bbox, dict):
                left = int(bbox.get("left", 0))
                top = int(bbox.get("top", 0))
                width = int(bbox.get("width", 0))
                height = int(bbox.get("height", 0))
                new_location = f"monitor {monitor} bbox left={left},top={top},w={width},h={height}"
            else:
                new_location = f"monitor {monitor} (detected)"
        except Exception:
            new_location = f"monitor {monitor} (detected)"
        now = datetime.now().isoformat()
        det_conf = float(confidence or 0.0)
        if not existing:
            # cria nova entrada
            full_context = (context or "") + " (structured_detection)"
            return self.remember_object_location(object_name, new_location, context=full_context, confidence=det_conf, room=room, area=area)
        try:
            existing_conf = float(existing["confidence"] or 0.0)
        except Exception:
            existing_conf = 0.0
        existing_loc = existing["location"] or ""
        existing_id = existing["id"]
        # det é significativamente mais confiável → sobrescreve
        if det_conf >= existing_conf + delta_threshold:
            prev = existing_loc
            merged_confidence = max(det_conf, existing_conf)
            full_context = (context or "") + f" (structured_detection overwrote previous='{prev}')"
            conn.execute(
                "UPDATE environment_objects SET location=?, room=?, area=?, context=?, confidence=?, last_seen_at=?, updated_at=? WHERE id=?",
                (new_location, (room or ""), (area or ""), full_context, merged_confidence, now, now, existing_id),
            )
            conn.commit()
            return dict(existing)
        # det contradiz memória forte: anotar e notificar
        if det_conf <= existing_conf - delta_threshold and det_conf >= 0.0 and existing_conf >= 0.8:
            # reduz levemente confiança existente e marca contradição no context
            new_conf = max(0.0, existing_conf * 0.9)
            contradiction_note = (
                f"contradiction detected at {now}: detection_conf={det_conf}, memory_conf={existing_conf}, detection_loc={new_location}, memory_loc={existing_loc}"
            )
            new_context = (existing["context"] or "") + "\n" + contradiction_note
            conn.execute(
                "UPDATE environment_objects SET context=?, confidence=?, updated_at=? WHERE id=?",
                (new_context, new_conf, now, existing_id),
            )
            conn.commit()
            # notifica frontend via inbox_entries
            title = f"Contradição detectada: {obj_key}"
            body = (
                f"Detectei {obj_key} em {new_location} (conf={det_conf}), mas a memória esperava {existing_loc} (conf={existing_conf}).\n"
                "Deseja que eu atualize a memória?"
            )
            try:
                self._notify_frontend(title, body)
            except Exception:
                pass
            # publish via in-memory SSE publisher if available
            try:
                from ..core.notification_pub import publish

                # best-effort: if publish is async, schedule it
                import asyncio as _asyncio

                _payload = {
                    "id": existing_id,
                    "title": title,
                    "body": body,
                    "created_at": now,
                }
                try:
                    # if called inside sync context, create task in running loop
                    loop = _asyncio.get_running_loop()
                    loop.create_task(publish(_payload))
                except RuntimeError:
                    # no running loop (sync test env); call publish via new loop
                    try:
                        _asyncio.run(publish(_payload))
                    except Exception:
                        pass
            except Exception:
                pass
            return dict(existing)
        # Merge / atualização leve: atualiza last_seen_at e confidence
        merged_conf = max(existing_conf, det_conf)
        merged_context = (existing["context"] or "") + "\n" + (context or "")
        conn.execute(
            "UPDATE environment_objects SET last_seen_at=?, confidence=?, context=?, updated_at=? WHERE id=?",
            (now, merged_conf, merged_context.strip(), now, existing_id),
        )
        conn.commit()
        return dict(existing)

    def find_object_location(self, object_name: str, room: str | None = None):
        object_key = self._normalize_object_name(object_name)
        if not object_key:
            return None
        conn = get_connection(self._db_path)
        if room:
            room_key = self._normalize_place_name(room)
            row = conn.execute(
                "SELECT * FROM environment_objects WHERE object_name = ? AND (room = ? OR area = ? OR location LIKE ?) ORDER BY updated_at DESC LIMIT 1",
                (object_key, room_key, room_key, f"%{room_key}%"),
            ).fetchone()
            if row:
                return dict(row)
        row = conn.execute(
            "SELECT * FROM environment_objects WHERE object_name = ? ORDER BY updated_at DESC LIMIT 1",
            (object_key,),
        ).fetchone()
        return dict(row) if row else None

    def find_objects_in_room(self, room: str | None = None, area: str | None = None, limit: int = 10):
        if not room and not area:
            return []
        room_key = self._normalize_place_name(room) if room else ""
        area_key = self._normalize_place_name(area) if area else ""
        conn = get_connection(self._db_path)
        if room_key and area_key:
            rows = conn.execute(
                "SELECT * FROM environment_objects WHERE (room = ? OR area = ? OR location LIKE ? OR room LIKE ? OR area LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                (room_key, area_key, f"%{room_key}%", f"%{room_key}%", f"%{area_key}%", limit),
            ).fetchall()
        elif room_key:
            rows = conn.execute(
                "SELECT * FROM environment_objects WHERE (room = ? OR room LIKE ? OR location LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                (room_key, f"%{room_key}%", f"%{room_key}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM environment_objects WHERE (area = ? OR area LIKE ? OR location LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                (area_key, f"%{area_key}%", f"%{area_key}%", limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def find_related_objects(self, query: str, limit: int = 3):
        text = self._normalize_object_name(query)
        if not text:
            return []
        tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t]
        if not tokens:
            return []
        conditions = []
        params = []
        for token in tokens[:3]:
            conditions.append("(object_name LIKE ? OR room LIKE ? OR area LIKE ? OR location LIKE ?)")
            params.extend([f"%{token}%", f"%{token}%", f"%{token}%", f"%{token}%"])
        where_clause = " OR ".join(conditions)
        conn = get_connection(self._db_path)
        rows = conn.execute(
            f"SELECT * FROM environment_objects WHERE {where_clause} ORDER BY updated_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]

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
