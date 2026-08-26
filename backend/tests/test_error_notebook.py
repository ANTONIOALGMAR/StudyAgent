"""Testes Phase 5: Caderno de erros e pipeline exercício→flashcards."""




# ── Error Notebook ─────────────────────────────────────────────────────────────


class TestErrorNotebook:
    def test_log_error(self, tmp_db):
        from app.tutor.error_notebook import get_errors_by_topic, log_error

        result = log_error(
            topic="frações",
            question="Quanto é 1/2 + 1/3?",
            user_answer="2/5",
            correct_answer="5/6",
            explanation="MMC de 2 e 3 é 6",
        )
        assert result["topic"] == "frações"
        errors = get_errors_by_topic("frações")
        assert len(errors) == 1
        assert errors[0]["correct_answer"] == "5/6"

    def test_log_errors_from_exercise(self, tmp_db):
        from app.tutor.error_notebook import get_errors_by_topic, log_errors_from_exercise

        results = [
            {"q": "Q1", "user_answer": "errado", "expected": "certo", "correct": False, "explanation": "exp1"},
            {"q": "Q2", "user_answer": "certo", "expected": "certo", "correct": True},
            {"q": "Q3", "user_answer": "errado2", "expected": "certo2", "correct": False, "explanation": "exp2"},
        ]
        count = log_errors_from_exercise("ex1", "álgebra", results)
        assert count == 2
        errors = get_errors_by_topic("álgebra")
        assert len(errors) == 2

    def test_get_errors_excludes_reviewed(self, tmp_db):
        from app.tutor.error_notebook import get_errors_by_topic, log_error, mark_reviewed

        log_error(topic="t1", question="Q1", user_answer="a", correct_answer="b")
        log_error(topic="t1", question="Q2", user_answer="c", correct_answer="d")
        all_errors = get_errors_by_topic("t1", include_reviewed=True)
        assert len(all_errors) == 2
        # all_errors is DESC, so [0]=Q2, [1]=Q1
        mark_reviewed(all_errors[0]["id"])  # mark Q2 reviewed
        pending = get_errors_by_topic("t1", include_reviewed=False)
        assert len(pending) == 1
        assert pending[0]["question"] == "Q1"

    def test_error_stats(self, tmp_db):
        from app.tutor.error_notebook import error_stats, log_error

        log_error(topic="frações", question="Q1", user_answer="a", correct_answer="b")
        log_error(topic="frações", question="Q2", user_answer="c", correct_answer="d")
        log_error(topic="álgebra", question="Q3", user_answer="e", correct_answer="f")
        stats = error_stats()
        assert stats["total_errors"] == 3
        assert stats["pending_review"] == 3
        assert len(stats["by_topic"]) == 2
        assert stats["by_topic"][0]["topic"] == "frações"
        assert stats["by_topic"][0]["count"] == 2

    def test_mark_reviewed(self, tmp_db):
        from app.tutor.error_notebook import get_errors_by_topic, log_error, mark_reviewed

        log_error(topic="t1", question="Q", user_answer="a", correct_answer="b")
        errors = get_errors_by_topic("t1")
        assert len(errors) == 1
        mark_reviewed(errors[0]["id"])
        pending = get_errors_by_topic("t1")
        assert len(pending) == 0

    def test_mark_topic_reviewed(self, tmp_db):
        from app.tutor.error_notebook import get_errors_by_topic, log_error, mark_topic_reviewed

        log_error(topic="história", question="Q1", user_answer="a", correct_answer="b")
        log_error(topic="história", question="Q2", user_answer="c", correct_answer="d")
        log_error(topic="geometria", question="Q3", user_answer="e", correct_answer="f")
        count = mark_topic_reviewed("história")
        assert count == 2
        pending_hist = get_errors_by_topic("história")
        assert len(pending_hist) == 0
        pending_geo = get_errors_by_topic("geometria")
        assert len(pending_geo) == 1

    def test_errors_for_flashcards(self, tmp_db):
        from app.tutor.error_notebook import errors_for_flashcards, log_error

        log_error(topic="mat", question="Q1", user_answer="a", correct_answer="b", explanation="exp1")
        log_error(topic="mat", question="Q2", user_answer="c", correct_answer="d")
        errors = errors_for_flashcards(topic="mat")
        assert len(errors) == 2
        assert errors[0]["question"] in ("Q1", "Q2")

    def test_errors_for_flashcards_all_topics(self, tmp_db):
        from app.tutor.error_notebook import errors_for_flashcards, log_error

        log_error(topic="A", question="Q1", user_answer="a", correct_answer="b")
        log_error(topic="B", question="Q2", user_answer="c", correct_answer="d")
        errors = errors_for_flashcards()
        assert len(errors) == 2


# ── Flashcards from Errors ────────────────────────────────────────────────────


class TestFlashcardsFromErrors:
    def test_generate_from_errors_empty(self, tmp_db):
        from app.tutor.flashcards import generate_from_errors

        result = generate_from_errors()
        assert result["card_count"] == 0
        assert "Nenhum erro" in result["message"]

    def test_generate_from_errors_with_data(self, tmp_db):
        from app.tutor.error_notebook import log_error
        from app.tutor.flashcards import generate_from_errors, list_decks

        log_error(topic="frações", question="Q1", user_answer="a", correct_answer="5/6", explanation="exp")
        log_error(topic="frações", question="Q2", user_answer="c", correct_answer="3/4")
        result = generate_from_errors(topic="frações")
        assert result["card_count"] == 2
        assert result["source"] == "error_notebook"
        decks = list_decks()
        assert any("erros" in d["title"] for d in decks)

    def test_generate_from_errors_marks_reviewed(self, tmp_db):
        from app.tutor.error_notebook import get_errors_by_topic, log_error
        from app.tutor.flashcards import generate_from_errors

        log_error(topic="hist", question="Q1", user_answer="a", correct_answer="b")
        generate_from_errors(topic="hist")
        pending = get_errors_by_topic("hist", include_reviewed=False)
        assert len(pending) == 0

    def test_generate_from_errors_limit(self, tmp_db):
        from app.tutor.error_notebook import log_error
        from app.tutor.flashcards import generate_from_errors

        for i in range(15):
            log_error(topic="mat", question=f"Q{i}", user_answer="a", correct_answer="b")
        result = generate_from_errors(topic="mat", limit=5)
        assert result["card_count"] == 5


# ── Mastery-Aware Study Plan ──────────────────────────────────────────────────


class TestMasteryAwarePlan:
    def test_build_mastery_hint_empty(self, tmp_db):
        from app.tutor.study_plan import _build_mastery_hint

        hint = _build_mastery_hint("nonexistent")
        assert hint == ""

    def test_build_mastery_hint_weak(self, tmp_db):
        from app.tutor.profile import update_from_exercise
        from app.tutor.study_plan import _build_mastery_hint

        for _ in range(3):
            update_from_exercise("frações", 1, 4, 25)
        hint = _build_mastery_hint("frações")
        assert "dificuldade" in hint.lower() or "mastery" in hint.lower()

    def test_build_mastery_hint_strong(self, tmp_db):
        from app.tutor.profile import update_from_exercise
        from app.tutor.study_plan import _build_mastery_hint

        for _ in range(4):
            update_from_exercise("geometria", 4, 4, 100, difficulty_level="muito difícil")
        hint = _build_mastery_hint("geometria")
        assert "domina" in hint.lower() or "avançado" in hint.lower()
