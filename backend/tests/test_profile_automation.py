"""Testes P6 (perfil + mastery) e P7 (automação com confirmação)."""


import pytest

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

    def test_sync_profile_name_from_face(self, tmp_db):
        from app.tutor.profile import get_profile, save_profile, sync_profile_name
        save_profile(name="Antiga", grade="8º ano", school="EMEF")
        synced = sync_profile_name("Ana Souza")
        assert synced["name"] == "Ana Souza"
        profile = get_profile()
        assert profile["name"] == "Ana Souza"
        assert profile["grade"] == "8º ano"
        assert profile["school"] == "EMEF"


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
        for _ in range(4):
            update_from_exercise("geometria", 4, 4, 100, difficulty_level="muito difícil")
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


# ── P3: Weighted Scoring ───────────────────────────────────────────────────────


class TestWeightedScoring:
    def test_weighted_score_populated_after_exercise(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        update_from_exercise("frações", 3, 4, 75)
        details = topic_details("frações")
        assert details is not None
        assert isinstance(details["weighted_score"], float)
        assert details["weighted_score"] > 0

    def test_weighted_score_populated_after_flashcard(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_flashcard_review
        update_from_flashcard_review("história", 4)
        details = topic_details("história")
        assert details is not None
        assert details["weighted_score"] > 0

    def test_high_difficulty_raises_weighted_score(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        # Two exercises at same percent but different difficulty
        update_from_exercise("easy_topic", 3, 4, 75, difficulty_level="fácil")
        update_from_exercise("easy_topic", 3, 4, 75, difficulty_level="fácil")
        update_from_exercise("hard_topic", 3, 4, 75, difficulty_level="muito difícil")
        update_from_exercise("hard_topic", 3, 4, 75, difficulty_level="muito difícil")
        easy = topic_details("easy_topic")
        hard = topic_details("hard_topic")
        assert hard["weighted_score"] > easy["weighted_score"]

    def test_consistent_scores_beat_volatile(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        # Consistent: always 70%
        for _ in range(4):
            update_from_exercise("consistent", 3, 4, 75)
        # Volatile: alternates 0% and 100%
        update_from_exercise("volatile", 0, 4, 0)
        update_from_exercise("volatile", 4, 4, 100)
        update_from_exercise("volatile", 0, 4, 0)
        update_from_exercise("volatile", 4, 4, 100)
        cons = topic_details("consistent")
        vol = topic_details("volatile")
        assert cons["weighted_score"] > vol["weighted_score"]

    def test_calculate_weighted_score_direct(self, tmp_db):
        from app.tutor.profile import calculate_weighted_score
        score = calculate_weighted_score("nonexistent")
        assert score == 0.0

    def test_classify_entries_include_weighted_score(self, tmp_db):
        from app.tutor.profile import classify_topics, update_from_exercise
        update_from_exercise("álgebra", 1, 4, 25)
        update_from_exercise("álgebra", 1, 4, 25)
        classification = classify_topics()
        all_entries = classification["weak"] + classification["strong"] + classification["neutral"]
        for entry in all_entries:
            assert "weighted_score" in entry
            assert "avg_percent" in entry

    def test_all_mastery_includes_weighted_score(self, tmp_db):
        from app.tutor.profile import all_mastery, update_from_exercise
        update_from_exercise("A", 3, 4, 75)
        mastery = all_mastery()
        assert len(mastery) == 1
        assert "weighted_score" in mastery[0]

    def test_profile_insights_uses_weighted_score(self, tmp_db):
        from app.tutor.profile import profile_insights, update_from_exercise
        update_from_exercise("frações", 1, 4, 25)
        update_from_exercise("frações", 1, 4, 25)
        insights = profile_insights()
        assert len(insights["weak_topics"]) >= 1
        assert "weighted_score" in insights["weak_topics"][0]

    def test_volume_increases_weighted_score(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        # Same percent, but more attempts = more volume = higher score
        for _ in range(2):
            update_from_exercise("low_vol", 3, 4, 75)
        for _ in range(8):
            update_from_exercise("high_vol", 3, 4, 75)
        low = topic_details("low_vol")
        high = topic_details("high_vol")
        assert high["weighted_score"] > low["weighted_score"]


# ── P3: Rolling Window ────────────────────────────────────────────────────────


class TestRollingWindow:
    def test_rolling_window_real_eviction(self, tmp_db):
        from app.tutor.advanced_profile import update_difficulty
        for _ in range(5):
            update_difficulty("math", 20)
        result = update_difficulty("math", 95)
        assert result["window_avg"] > 20

    def test_rolling_window_limits_to_window_size(self, tmp_db):
        from app.tutor.advanced_profile import WINDOW_SIZE, get_adaptive_difficulty, update_difficulty
        for i in range(10):
            update_difficulty("topic", i * 10)
        update_difficulty("topic", 50)
        diff = get_adaptive_difficulty("topic")
        assert diff["window_count"] <= WINDOW_SIZE

    def test_difficulty_level_adapts(self, tmp_db):
        from app.tutor.advanced_profile import update_difficulty
        # All low scores → easy
        for _ in range(3):
            update_difficulty("easy", 20)
        result = update_difficulty("easy", 20)
        assert result["current_level"] == "muito fácil"

        # All high scores → hard
        for _ in range(3):
            update_difficulty("hard", 95)
        result = update_difficulty("hard", 95)
        assert result["current_level"] == "muito difícil"

    def test_topic_results_stored(self, tmp_db):
        from app.tutor.profile import topic_details, update_from_exercise
        update_from_exercise("stored_topic", 3, 4, 75, difficulty_level="difícil")
        details = topic_details("stored_topic")
        assert details is not None
        assert details["weighted_score"] > 0

    def test_recommend_uses_weighted_score(self, tmp_db):
        from app.tutor.advanced_profile import recommend_for_time
        from app.tutor.profile import update_from_exercise

        # Create a clearly weak topic
        for _ in range(3):
            update_from_exercise("fraco", 1, 4, 25)
        result = recommend_for_time(30)
        types = [s["type"] for s in result["suggestions"]]
        assert "exercise" in types


# ── Phase 4: Student Dashboard ────────────────────────────────────────────────


class TestStudentDashboard:
    def test_empty_dashboard(self, tmp_db):
        from app.tutor.profile import student_dashboard
        result = student_dashboard()
        assert result == ""

    def test_dashboard_with_weak_topics(self, tmp_db):
        from app.tutor.profile import student_dashboard, update_from_exercise
        for _ in range(3):
            update_from_exercise("frações", 1, 4, 25)
        dashboard = student_dashboard()
        assert "Dashboard do aluno" in dashboard
        assert "Pontos fracos" in dashboard
        assert "frações" in dashboard

    def test_dashboard_with_strong_topics(self, tmp_db):
        from app.tutor.profile import student_dashboard, update_from_exercise
        for _ in range(4):
            update_from_exercise("geometria", 4, 4, 100, difficulty_level="muito difícil")
        dashboard = student_dashboard()
        assert "Fortes" in dashboard
        assert "geometria" in dashboard

    def test_dashboard_with_recent_exercises(self, tmp_db):
        from app.tutor.profile import student_dashboard, update_from_exercise
        update_from_exercise("história", 3, 4, 75)
        dashboard = student_dashboard()
        assert "Últimos exercícios" in dashboard
        assert "história" in dashboard

    def test_dashboard_shows_streak(self, tmp_db):
        from app.tutor.profile import student_dashboard, update_from_exercise
        update_from_exercise("mat", 3, 4, 75)
        dashboard = student_dashboard()
        assert "Streak:" in dashboard
        assert "Temas estudados:" in dashboard

    def test_dashboard_limits_weak_to_3(self, tmp_db):
        from app.tutor.profile import student_dashboard, update_from_exercise
        for topic in ["A", "B", "C", "D"]:
            for _ in range(3):
                update_from_exercise(topic, 1, 4, 25)
        dashboard = student_dashboard()
        # Should only show 3 weak topics max
        assert dashboard.count("Pontos fracos:") == 1

    def test_dashboard_is_concise(self, tmp_db):
        from app.tutor.profile import student_dashboard, update_from_exercise
        for _ in range(3):
            update_from_exercise("tema", 3, 4, 75)
        dashboard = student_dashboard()
        lines = dashboard.strip().split("\n")
        assert len(lines) <= 6
