"""Testes P6 (perfil + mastery) e P7 (automação com confirmação)."""

import sqlite3
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS student_profile (
            id TEXT PRIMARY KEY, name TEXT, grade TEXT, school TEXT,
            preferences TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS topic_mastery (
            topic TEXT PRIMARY KEY, attempts INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0, total_questions INTEGER DEFAULT 0,
            avg_percent INTEGER DEFAULT 0, last_practiced TEXT,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS action_proposals (
            id TEXT PRIMARY KEY, action_type TEXT NOT NULL,
            params TEXT DEFAULT '{}', description TEXT DEFAULT '',
            status TEXT DEFAULT 'pending', rejection_reason TEXT DEFAULT '',
            created_at TEXT NOT NULL, resolved_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()

    with patch("app.tutor.profile.MEMORY_DB_PATH", db_path), \
         patch("app.tutor.automation.MEMORY_DB_PATH", db_path):
        yield db_path


# ── P6: Profile ────────────────────────────────────────────────────────────────


class TestProfile:
    def test_get_profile_empty(self, tmp_db):
        from app.tutor.profile import get_profile
        assert get_profile() is None

    def test_save_and_get_profile(self, tmp_db):
        from app.tutor.profile import get_profile, save_profile
        result = save_profile(name="Ana", grade="9º ano", school="EMEF Paulo")
        assert result["name"] == "Ana"
        profile = get_profile()
        assert profile is not None
        assert profile["name"] == "Ana"
        assert profile["grade"] == "9º ano"

    def test_update_profile(self, tmp_db):
        from app.tutor.profile import get_profile, save_profile
        save_profile(name="Ana")
        save_profile(name="Ana Silva", grade="9º ano")
        profile = get_profile()
        assert profile["name"] == "Ana Silva"
        assert profile["grade"] == "9º ano"


# ── P6: Topic Mastery ──────────────────────────────────────────────────────────


class TestTopicMastery:
    def test_update_from_exercise_creates_entry(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        update_from_exercise("frações", 3, 4, 75)
        details = topic_details("frações")
        assert details is not None
        assert details["attempts"] == 1
        assert details["correct"] == 3
        assert details["avg_percent"] == 75

    def test_update_from_exercise_increments(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        update_from_exercise("frações", 3, 4, 75)
        update_from_exercise("frações", 2, 4, 50)
        details = topic_details("frações")
        assert details["attempts"] == 2
        assert details["correct"] == 5
        assert details["total_questions"] == 8
        assert details["avg_percent"] == 62  # 5/8 = 62.5 → 62

    def test_update_from_flashcard_review(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_flashcard_review
        update_from_flashcard_review("história", 4)  # good
        update_from_flashcard_review("história", 1)  # again
        details = topic_details("história")
        assert details["attempts"] == 2
        assert details["correct"] == 1
        assert details["avg_percent"] == 50

    def test_classify_topics_weak(self, tmp_db):
        from app.tutor.profile import classify_topics, update_from_exercise
        update_from_exercise("álgebra", 1, 4, 25)
        update_from_exercise("álgebra", 1, 4, 25)
        classification = classify_topics()
        weak = [w["topic"] for w in classification["weak"]]
        assert "álgebra" in weak

    def test_classify_topics_strong(self, tmp_db):
        from app.tutor.profile import classify_topics, update_from_exercise
        update_from_exercise("geometria", 4, 4, 100)
        update_from_exercise("geometria", 4, 4, 100)
        classification = classify_topics()
        strong = [s["topic"] for s in classification["strong"]]
        assert "geometria" in strong

    def test_suggest_review_returns_weak(self, tmp_db):
        from app.tutor.profile import suggest_review, update_from_exercise
        update_from_exercise("frações", 1, 4, 25)
        update_from_exercise("frações", 1, 4, 25)
        suggestions = suggest_review()
        topics = [s["topic"] for s in suggestions]
        assert "frações" in topics

    def test_all_mastery(self, tmp_db):
        from app.tutor.profile import all_mastery, update_from_exercise
        update_from_exercise("A", 3, 4, 75)
        update_from_exercise("B", 1, 4, 25)
        mastery = all_mastery()
        assert len(mastery) == 2

    def test_profile_insights(self, tmp_db):
        from app.tutor.profile import profile_insights, save_profile, update_from_exercise
        save_profile(name="Ana", grade="9º")
        update_from_exercise("frações", 1, 4, 25)
        update_from_exercise("frações", 1, 4, 25)
        insights = profile_insights()
        assert insights["profile"]["name"] == "Ana"
        assert len(insights["weak_topics"]) >= 1
        assert insights["total_topics_studied"] >= 1


# ── P7: Automation ─────────────────────────────────────────────────────────────


class TestAutomation:
    def test_create_proposal(self, tmp_db):
        from app.tutor.automation import create_proposal
        result = create_proposal("generate_exercises", {"topic": "frações"}, "Gerar exercícios")
        assert result["status"] == "pending"
        assert result["action_type"] == "generate_exercises"
        assert result["params"]["topic"] == "frações"

    def test_create_invalid_proposal(self, tmp_db):
        from app.tutor.automation import create_proposal
        with pytest.raises(ValueError):
            create_proposal("invalid_type", {})

    def test_approve_proposal(self, tmp_db):
        from app.tutor.automation import approve, create_proposal
        p = create_proposal("generate_flashcards", {"topic": "história"})
        result = approve(p["proposal_id"])
        assert result["status"] == "approved"
        assert result["action_type"] == "generate_flashcards"

    def test_reject_proposal(self, tmp_db):
        from app.tutor.automation import create_proposal, reject
        p = create_proposal("web_search", {"query": "matemática"})
        result = reject(p["proposal_id"], reason="Não quero pesquisar")
        assert result["status"] == "rejected"

    def test_approve_already_processed(self, tmp_db):
        from app.tutor.automation import approve, create_proposal, reject
        p = create_proposal("open_url", {"url": "http://example.com"})
        reject(p["proposal_id"])
        result = approve(p["proposal_id"])
        assert result["status"] == "rejected"

    def test_get_pending(self, tmp_db):
        from app.tutor.automation import approve, create_proposal, get_pending
        create_proposal("generate_exercises", {"topic": "A"})
        create_proposal("web_search", {"query": "B"})
        pending = get_pending()
        assert len(pending) == 2
        approve(pending[0]["id"])
        pending = get_pending()
        assert len(pending) == 1

    def test_inject_proposal_prompt(self, tmp_db):
        from app.tutor.automation import inject_proposal_prompt
        prompt = inject_proposal_prompt()
        assert "generate_exercises" in prompt
        assert "action" in prompt
