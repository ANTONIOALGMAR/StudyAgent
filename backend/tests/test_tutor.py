"""Testes do módulo tutor: SM-2, flashcards, study plans, stats."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# ─── SM-2 algorithm ────────────────────────────────────────────────────────────


class TestSM2:
    def test_first_good_answer(self):
        from app.tutor.flashcards import sm2_next

        easiness, interval, reps = sm2_next(2.5, 1, 0, quality=3)
        assert reps == 1
        assert interval == 1
        assert easiness >= 1.3

    def test_perfect_answer_first_time(self):
        from app.tutor.flashcards import sm2_next

        easiness, interval, reps = sm2_next(2.5, 1, 0, quality=5)
        assert reps == 1
        assert interval == 1
        assert easiness > 2.5

    def test_wrong_answer_resets(self):
        from app.tutor.flashcards import sm2_next

        easiness, interval, reps = sm2_next(2.5, 20, 5, quality=1)
        assert reps == 0
        assert interval == 1

    def test_easiness_never_below_minimum(self):
        from app.tutor.flashcards import MIN_EASINESS, sm2_next

        e = 2.5
        for _ in range(30):
            e, _, _ = sm2_next(e, 1, 0, quality=0)
        assert e >= MIN_EASINESS

    def test_interval_grows_on_good_streak(self):
        from app.tutor.flashcards import sm2_next

        e, intv, reps = 2.5, 1, 0
        intervals = []
        for _ in range(6):
            e, intv, reps = sm2_next(e, intv, reps, quality=4)
            intervals.append(intv)
        # After quality=3 threshold: reps go 1→2→3→4→5→6
        # intervals: 1, 6, round(6*e), round(prev*e)...
        assert intervals[0] == 1   # first good: reps=1
        assert intervals[1] == 6   # second good: reps=2
        assert intervals[2] > 6    # third good: reps=3, interval grows

    def test_quality_clamping_low(self):
        from app.tutor.flashcards import sm2_next

        e1, _, _ = sm2_next(2.5, 1, 0, quality=-5)
        e2, _, _ = sm2_next(2.5, 1, 0, quality=0)
        assert e1 == e2  # both clamp to 0

    def test_quality_clamping_high(self):
        from app.tutor.flashcards import sm2_next

        e1, _, _ = sm2_next(2.5, 1, 0, quality=10)
        e2, _, _ = sm2_next(2.5, 1, 0, quality=5)
        assert e1 == e2  # both clamp to 5

    def test_quality_from_difficulty(self):
        from app.tutor.flashcards import quality_from_difficulty

        assert quality_from_difficulty("again") == 1
        assert quality_from_difficulty("hard") == 2
        assert quality_from_difficulty("good") == 3
        assert quality_from_difficulty("easy") == 5
        assert quality_from_difficulty("unknown") == 3


# ─── Flashcard CRUD (with temp DB) ────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    """Create a fresh temp DB and patch MEMORY_DB_PATH in all tutor modules."""
    db_path = tmp_path / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # create all tables in the temp DB
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS flashcard_decks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, topic TEXT,
            source_doc TEXT, card_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS flashcards (
            id TEXT PRIMARY KEY, deck_id TEXT NOT NULL,
            front TEXT NOT NULL, back TEXT NOT NULL,
            easiness REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 1,
            repetitions INTEGER NOT NULL DEFAULT 0,
            next_review TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS flashcard_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL, quality INTEGER NOT NULL,
            reviewed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS study_plans (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, topic TEXT NOT NULL,
            total_items INTEGER NOT NULL DEFAULT 0,
            done_items INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS study_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id TEXT NOT NULL, title TEXT NOT NULL,
            detail TEXT, done INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS exercise_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id TEXT NOT NULL, topic TEXT NOT NULL,
            score INTEGER NOT NULL, total INTEGER NOT NULL,
            percent INTEGER NOT NULL, level TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    with patch("app.tutor.flashcards.MEMORY_DB_PATH", db_path), \
         patch("app.tutor.study_plan.MEMORY_DB_PATH", db_path), \
         patch("app.tutor.stats.MEMORY_DB_PATH", db_path):
        yield db_path


class TestFlashcardCRUD:
    def _seed_deck(self, db_path):
        import uuid

        deck_id = uuid.uuid4().hex[:10]
        now = datetime.now().isoformat()
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO flashcard_decks (id,title,topic,card_count,created_at) VALUES (?,?,?,?,?)",
            (deck_id, "álgebra", "álgebra", 2, now),
        )
        c1 = uuid.uuid4().hex[:8]
        c2 = uuid.uuid4().hex[:8]
        conn.execute(
            "INSERT INTO flashcards (id,deck_id,front,back,easiness,interval_days,"
            "repetitions,next_review,created_at) VALUES (?,?,?,?,2.5,1,0,?,?)",
            (c1, deck_id, "O que é x?", "Variável", now, now),
        )
        conn.execute(
            "INSERT INTO flashcards (id,deck_id,front,back,easiness,interval_days,"
            "repetitions,next_review,created_at) VALUES (?,?,?,?,2.5,1,0,?,?)",
            (c2, deck_id, "2+2?", "4", now, now),
        )
        conn.commit()
        conn.close()
        return deck_id

    def test_list_decks(self, tmp_db):
        from app.tutor.flashcards import list_decks

        self._seed_deck(tmp_db)
        decks = list_decks()
        assert len(decks) == 1
        assert decks[0]["topic"] == "álgebra"

    def test_due_cards(self, tmp_db):
        from app.tutor.flashcards import due_cards

        deck_id = self._seed_deck(tmp_db)
        due = due_cards(deck_id)
        assert len(due) == 2

    def test_due_cards_future_not_included(self, tmp_db):
        from app.tutor.flashcards import due_cards

        deck_id = self._seed_deck(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        future = (datetime.now() + timedelta(days=30)).isoformat()
        conn.execute(
            "UPDATE flashcards SET next_review = ? WHERE deck_id = ?",
            (future, deck_id),
        )
        conn.commit()
        conn.close()
        due = due_cards(deck_id)
        assert len(due) == 0

    def test_review_card(self, tmp_db):
        from app.tutor.flashcards import due_cards, review_card

        deck_id = self._seed_deck(tmp_db)
        due = due_cards(deck_id)
        card_id = due[0]["id"]
        result = review_card(card_id, "good")
        assert result["card_id"] == card_id
        assert result["difficulty"] == "good"
        assert result["interval_days"] >= 1
        remaining = due_cards(deck_id)
        assert len(remaining) == 1

    def test_review_card_wrong_resets(self, tmp_db):
        from app.tutor.flashcards import review_card

        self._seed_deck(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        future = (datetime.now() + timedelta(days=30)).isoformat()
        card_id = conn.execute("SELECT id FROM flashcards LIMIT 1").fetchone()[0]
        conn.execute(
            "UPDATE flashcards SET repetitions=5, interval_days=30, next_review=? WHERE id=?",
            (future, card_id),
        )
        conn.commit()
        conn.close()
        result = review_card(card_id, "again")
        assert result["interval_days"] == 1
        # next_review = now + 1 day (interval=1 after reset)
        expected_max = (datetime.now() + timedelta(days=2)).isoformat()
        assert result["next_review"] <= expected_max

    def test_deck_stats(self, tmp_db):
        from app.tutor.flashcards import deck_stats

        deck_id = self._seed_deck(tmp_db)
        stats = deck_stats(deck_id)
        assert stats["total"] == 2
        assert stats["due"] == 2
        assert stats["learned"] == 0

    def test_review_nonexistent_raises(self, tmp_db):
        from app.tutor.flashcards import review_card

        with pytest.raises(KeyError):
            review_card("nonexistent", "good")


# ─── Study Plan CRUD ───────────────────────────────────────────────────────────


class TestStudyPlan:
    def test_list_plans_empty(self, tmp_db):
        from app.tutor.study_plan import list_plans

        assert list_plans() == []

    def test_get_nonexistent_plan(self, tmp_db):
        from app.tutor.study_plan import get_plan

        assert get_plan("nonexistent") is None

    def test_toggle_item(self, tmp_db):
        from app.tutor.study_plan import toggle_item

        conn = sqlite3.connect(str(tmp_db))
        conn.execute(
            "INSERT INTO study_plans (id,title,topic,total_items,done_items,created_at) "
            "VALUES ('p1','Teste','mat',2,0,?)",
            (datetime.now().isoformat(),),
        )
        conn.execute(
            "INSERT INTO study_items (plan_id,title,detail,done,sort_order) "
            "VALUES ('p1','Item 1','det',0,0)"
        )
        conn.execute(
            "INSERT INTO study_items (plan_id,title,detail,done,sort_order) "
            "VALUES ('p1','Item 2','det',0,1)"
        )
        conn.commit()
        conn.close()

        result = toggle_item(1)
        assert result["done"] is True
        assert result["done_items"] == 1
        assert result["total_items"] == 2

        result = toggle_item(1)
        assert result["done"] is False
        assert result["done_items"] == 0

    def test_toggle_nonexistent_raises(self, tmp_db):
        from app.tutor.study_plan import toggle_item

        with pytest.raises(KeyError):
            toggle_item(99999)


# ─── Stats ─────────────────────────────────────────────────────────────────────


class TestStats:
    def test_dashboard_empty(self, tmp_db):
        from app.tutor.stats import dashboard

        d = dashboard()
        assert d["exercises"]["total_sessions"] == 0
        assert d["flashcards"]["total_decks"] == 0
        assert d["study_plans"]["total_plans"] == 0

    def test_save_exercise_result(self, tmp_db):
        from app.tutor.stats import exercise_stats, save_exercise_result

        save_exercise_result("ex1", "frações", 3, 4, 75, "fundamental")
        stats = exercise_stats()
        assert stats["total_sessions"] == 1
        assert stats["avg_percent"] == 75.0
        assert stats["total_correct"] == 3

    def test_streak_counts_today(self, tmp_db):
        from app.tutor.stats import exercise_stats, save_exercise_result

        save_exercise_result("ex1", "tema", 2, 4, 50, "")
        stats = exercise_stats()
        assert stats["streak_days"] >= 1
