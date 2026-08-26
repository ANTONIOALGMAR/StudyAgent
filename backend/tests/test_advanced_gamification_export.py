"""Testes P8 (perfil avançado), P9 (gamificação) e P10 (export/import)."""

import sqlite3

import pytest


def _insert_exercise(conn, topic, score, total, percent):
    from datetime import datetime
    conn.execute(
        "INSERT INTO exercise_history (exercise_id, topic, score, total, percent, level, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"ex_{topic}_{score}", topic, score, total, percent, "médio", datetime.now().isoformat()),
    )
    conn.commit()


# ── P8: Session Log ────────────────────────────────────────────────────────────


class TestSessionLog:
    def test_start_and_end_session(self, tmp_db):
        from app.tutor.advanced_profile import end_session, start_session
        sid = start_session("exercise", {"topic": "frações"})
        assert len(sid) == 10
        result = end_session(sid)
        assert result["duration_seconds"] >= 0

    def test_end_nonexistent_session(self, tmp_db):
        from app.tutor.advanced_profile import end_session
        with pytest.raises(KeyError):
            end_session("nonexistent")

    def test_end_session_idempotent(self, tmp_db):
        from app.tutor.advanced_profile import end_session, start_session
        sid = start_session("chat")
        r1 = end_session(sid)
        r2 = end_session(sid)
        assert r1["duration_seconds"] == r2["duration_seconds"]


# ── P8: Time Analytics ─────────────────────────────────────────────────────────


class TestTimeAnalytics:
    def test_empty_analytics(self, tmp_db):
        from app.tutor.advanced_profile import time_analytics
        result = time_analytics()
        assert result["total_sessions"] == 0
        assert result["total_study_minutes"] == 0

    def test_with_sessions(self, tmp_db):
        from app.tutor.advanced_profile import end_session, start_session, time_analytics
        sid1 = start_session("exercise")
        end_session(sid1)
        sid2 = start_session("flashcard_review")
        end_session(sid2)
        result = time_analytics()
        assert result["total_sessions"] == 2
        assert result["total_study_minutes"] >= 0


# ── P8: Recommendations ────────────────────────────────────────────────────────


class TestRecommendations:
    def test_recommend_empty(self, tmp_db):
        from app.tutor.advanced_profile import recommend_for_time
        result = recommend_for_time(30)
        assert result["available_minutes"] == 30
        assert len(result["suggestions"]) >= 1
        assert result["suggestions"][0]["type"] == "free_study"

    def test_recommend_with_due_cards(self, tmp_db):
        from datetime import datetime, timedelta

        from app.tutor.advanced_profile import recommend_for_time
        conn = sqlite3.connect(str(tmp_db))
        now = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute(
            "INSERT INTO flashcard_decks (id, title, topic, card_count, created_at) VALUES (?, ?, ?, ?, ?)",
            ("deck1", "Test", "math", 3, now),
        )
        for i in range(3):
            conn.execute(
                "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
                "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 1, 0, ?, ?)",
                (f"c{i}", "deck1", f"Q{i}?", f"A{i}", now, now),
            )
        conn.commit()
        conn.close()
        result = recommend_for_time(30)
        types = [s["type"] for s in result["suggestions"]]
        assert "flashcards" in types


# ── P8: Adaptive Difficulty ────────────────────────────────────────────────────


class TestAdaptiveDifficulty:
    def test_get_default(self, tmp_db):
        from app.tutor.advanced_profile import get_adaptive_difficulty
        result = get_adaptive_difficulty("álgebra")
        assert result["current_level"] == "médio"
        assert result["window_avg"] == 50.0

    def test_update_difficulty_low(self, tmp_db):
        from app.tutor.advanced_profile import update_difficulty
        result = update_difficulty("álgebra", 20)
        assert result["current_level"] == "muito fácil"

    def test_update_difficulty_high(self, tmp_db):
        from app.tutor.advanced_profile import update_difficulty
        result = update_difficulty("geometria", 95)
        assert result["current_level"] == "muito difícil"

    def test_update_difficulty_medium(self, tmp_db):
        from app.tutor.advanced_profile import update_difficulty
        result = update_difficulty("frações", 60)
        assert result["current_level"] == "médio"

    def test_difficulty_for_generation(self, tmp_db):
        from app.tutor.advanced_profile import difficulty_for_generation, update_difficulty
        update_difficulty("história", 30)
        level = difficulty_for_generation("história")
        assert level == "fácil"


# ── P9: Achievements ──────────────────────────────────────────────────────────


class TestAchievements:
    def test_list_achievements(self, tmp_db):
        from app.tutor.gamification import list_achievements
        result = list_achievements()
        assert len(result) >= 15
        assert all("earned" in a for a in result)
        assert all(a["earned"] is False for a in result)

    def test_check_first_exercise(self, tmp_db):
        from app.tutor.gamification import check_achievements
        newly = check_achievements()
        assert len(newly) == 0  # no exercises yet

        # Insert an exercise
        conn = sqlite3.connect(str(tmp_db))
        _insert_exercise(conn, "math", 3, 4, 75)
        conn.close()

        newly = check_achievements()
        ids = [a["id"] for a in newly]
        assert "first_exercise" in ids

    def test_check_10_exercises(self, tmp_db):
        from app.tutor.gamification import check_achievements
        conn = sqlite3.connect(str(tmp_db))
        for i in range(10):
            _insert_exercise(conn, f"topic_{i}", 3, 4, 75)
        conn.close()
        newly = check_achievements()
        ids = [a["id"] for a in newly]
        assert "first_exercise" in ids
        assert "exercises_10" in ids

    def test_check_perfect_score(self, tmp_db):
        from app.tutor.gamification import check_achievements
        conn = sqlite3.connect(str(tmp_db))
        _insert_exercise(conn, "math", 4, 4, 100)
        conn.close()
        newly = check_achievements()
        ids = [a["id"] for a in newly]
        assert "perfect_score" in ids

    def test_check_first_deck(self, tmp_db):
        from app.tutor.gamification import check_achievements
        conn = sqlite3.connect(str(tmp_db))
        from datetime import datetime
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO flashcard_decks (id, title, topic, card_count, created_at) VALUES (?, ?, ?, ?, ?)",
            ("d1", "Test", "math", 5, now),
        )
        conn.commit()
        conn.close()
        newly = check_achievements()
        ids = [a["id"] for a in newly]
        assert "first_flashcard" in ids

    def test_earned_persists(self, tmp_db):
        from app.tutor.gamification import check_achievements, list_achievements
        conn = sqlite3.connect(str(tmp_db))
        _insert_exercise(conn, "math", 3, 4, 75)
        conn.close()
        check_achievements()
        achievements = list_achievements()
        earned = [a for a in achievements if a["id"] == "first_exercise"]
        assert len(earned) == 1
        assert earned[0]["earned"] is True

    def test_achievement_progress(self, tmp_db):
        from app.tutor.gamification import achievement_progress
        result = achievement_progress()
        assert "locked" in result
        assert "total" in result
        assert result["total"] >= 15
        assert result["earned"] == 0


# ── P9: Topic Streaks ─────────────────────────────────────────────────────────


class TestTopicStreaks:
    def test_empty_streaks(self, tmp_db):
        from app.tutor.gamification import topic_streaks
        result = topic_streaks()
        assert len(result) == 0

    def test_with_exercises(self, tmp_db):
        from app.tutor.gamification import topic_streaks
        conn = sqlite3.connect(str(tmp_db))
        _insert_exercise(conn, "fractions", 3, 4, 75)
        _insert_exercise(conn, "fractions", 2, 4, 50)
        conn.close()
        result = topic_streaks()
        assert len(result) == 1
        assert result[0]["topic"] == "fractions"
        assert result[0]["days_practiced"] == 1
        assert result[0]["current_streak"] == 1


# ── P10: Export CSV ────────────────────────────────────────────────────────────


class TestExportCSV:
    def test_export_deck_csv(self, tmp_db):
        from app.tutor.export_import import export_deck_csv
        conn = sqlite3.connect(str(tmp_db))
        from datetime import datetime
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO flashcard_decks (id, title, topic, card_count, created_at) VALUES (?, ?, ?, ?, ?)",
            ("d1", "Álgebra", "álgebra", 2, now),
        )
        conn.execute(
            "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
            "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 1, 0, ?, ?)",
            ("c1", "d1", "O que é x?", "Incerteza", now, now),
        )
        conn.execute(
            "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
            "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 1, 0, ?, ?)",
            ("c2", "d1", "2+2=?", "4", now, now),
        )
        conn.commit()
        conn.close()
        csv = export_deck_csv("d1")
        assert "#separator:tab" in csv
        assert "#deck:álgebra" in csv
        assert "O que é x?" in csv
        assert "4" in csv

    def test_export_nonexistent(self, tmp_db):
        from app.tutor.export_import import export_deck_csv
        with pytest.raises(KeyError):
            export_deck_csv("nonexistent")


# ── P10: Export JSON ───────────────────────────────────────────────────────────


class TestExportJSON:
    def test_export_deck_json(self, tmp_db):
        from app.tutor.export_import import export_deck_json
        conn = sqlite3.connect(str(tmp_db))
        from datetime import datetime
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO flashcard_decks (id, title, topic, card_count, created_at) VALUES (?, ?, ?, ?, ?)",
            ("d1", "Geometria", "geometria", 1, now),
        )
        conn.execute(
            "INSERT INTO flashcards (id, deck_id, front, back, easiness, interval_days, "
            "repetitions, next_review, created_at) VALUES (?, ?, ?, ?, 2.5, 6, 2, ?, ?)",
            ("c1", "d1", "Área do quadrado?", "lado²", now, now),
        )
        conn.commit()
        conn.close()
        result = export_deck_json("d1")
        assert result["format"] == "studyagent_v1"
        assert result["deck"]["topic"] == "geometria"
        assert len(result["cards"]) == 1

    def test_export_plan_json(self, tmp_db):
        from app.tutor.export_import import export_plan_json
        conn = sqlite3.connect(str(tmp_db))
        from datetime import datetime
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO study_plans (id, title, topic, total_items, done_items, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "Plano de Mat", "álgebra", 2, 1, now),
        )
        conn.execute(
            "INSERT INTO study_items (plan_id, title, detail, done, sort_order) VALUES (?, ?, ?, ?, ?)",
            ("p1", "Revisar equações", "Item 1", 1, 0),
        )
        conn.execute(
            "INSERT INTO study_items (plan_id, title, detail, done, sort_order) VALUES (?, ?, ?, ?, ?)",
            ("p1", "Fazer exercícios", "Item 2", 0, 1),
        )
        conn.commit()
        conn.close()
        result = export_plan_json("p1")
        assert result["format"] == "studyagent_v1"
        assert result["plan"]["title"] == "Plano de Mat"
        assert len(result["items"]) == 2


# ── P10: Import CSV ────────────────────────────────────────────────────────────


class TestImportCSV:
    def test_import_csv(self, tmp_db):
        from app.tutor.export_import import import_deck_csv
        csv_content = "front\tback\nO que é Python?\tLinguagem de programação\n2+2?\t4\n"
        result = import_deck_csv(csv_content, "programação", "Python Básico")
        assert result["card_count"] == 2
        assert result["topic"] == "programação"

    def test_import_csv_with_headers(self, tmp_db):
        from app.tutor.export_import import import_deck_csv
        csv_content = "#separator:tab\n#deck:test\nO que é HTTP?\tProtocolo web\n"
        result = import_deck_csv(csv_content, "redes")
        assert result["card_count"] == 1

    def test_import_empty_csv(self, tmp_db):
        from app.tutor.export_import import import_deck_csv
        with pytest.raises(ValueError):
            import_deck_csv("", "topic")

    def test_import_json(self, tmp_db):
        import json

        from app.tutor.export_import import import_deck_json
        data = {
            "format": "studyagent_v1",
            "deck": {"title": "Test", "topic": "math"},
            "cards": [{"front": "Q1?", "back": "A1"}],
        }
        result = import_deck_json(json.dumps(data))
        assert result["card_count"] == 1
        assert result["topic"] == "math"


# ── P10: Full Profile Export/Import ────────────────────────────────────────────


class TestFullExportImport:
    def test_export_full(self, tmp_db):
        from app.tutor.export_import import export_full
        conn = sqlite3.connect(str(tmp_db))
        from datetime import datetime
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO student_profile (id, name, grade, school, preferences, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("student1", "Ana", "9º", "EMEF", "", now, now),
        )
        conn.commit()
        conn.close()
        result = export_full()
        assert result["format"] == "studyagent_full_v1"
        assert result["profile"]["name"] == "Ana"

    def test_import_full(self, tmp_db):
        from app.tutor.export_import import import_full
        from app.tutor.profile import get_profile
        data = {
            "format": "studyagent_full_v1",
            "profile": {"name": "Carlos", "grade": "7º", "school": "EMEF", "preferences": ""},
            "mastery": [],
            "decks": [],
            "plans": [],
        }
        result = import_full(data)
        assert result["profile"] is True
        profile = get_profile()
        assert profile["name"] == "Carlos"


# ── Phase 8: XP System & Levels ─────────────────────────────────────────────────


class TestXPSystem:
    def test_award_xp(self, tmp_db):
        from app.tutor.gamification import award_xp
        result = award_xp(10, "test", "test xp")
        assert result["xp_gained"] == 10
        assert result["source"] == "test"
        assert "level" in result

    def test_award_xp_accumulates(self, tmp_db):
        from app.tutor.gamification import award_xp, get_level_info
        award_xp(50, "test")
        award_xp(30, "test")
        info = get_level_info()
        assert info["total_xp"] == 80
        assert info["level"] == "Iniciante"

    def test_award_exercise_xp(self, tmp_db):
        from app.tutor.gamification import award_exercise_xp
        result = award_exercise_xp(3, 4, "médio")
        assert result["xp_gained"] > 0
        assert result["source"] == "exercise"

    def test_award_exercise_xp_perfect(self, tmp_db):
        from app.tutor.gamification import award_exercise_xp, get_level_info
        award_exercise_xp(4, 4, "médio")
        info = get_level_info()
        assert info["total_xp"] > 0

    def test_award_flashcard_xp(self, tmp_db):
        from app.tutor.gamification import award_flashcard_xp
        result = award_flashcard_xp(True)
        assert result["xp_gained"] == 5
        result = award_flashcard_xp(False)
        assert result["xp_gained"] == 2

    def test_award_streak_xp(self, tmp_db):
        from app.tutor.gamification import award_streak_xp
        result = award_streak_xp(2)
        assert result["xp_gained"] == 0
        result = award_streak_xp(5)
        assert result["xp_gained"] > 0

    def test_award_plan_xp(self, tmp_db):
        from app.tutor.gamification import award_plan_xp
        result = award_plan_xp(False)
        assert result["xp_gained"] == 0
        result = award_plan_xp(True)
        assert result["xp_gained"] == 50

    def test_level_progression(self, tmp_db):
        from app.tutor.gamification import award_xp, get_level_info
        award_xp(100, "test")
        info = get_level_info()
        assert info["level"] == "Estudante"
        assert info["next_level"] == "Graduado"
        assert info["xp_to_next"] == 200

    def test_level_graduado(self, tmp_db):
        from app.tutor.gamification import award_xp, get_level_info
        award_xp(300, "test")
        info = get_level_info()
        assert info["level"] == "Graduado"

    def test_level_mestre(self, tmp_db):
        from app.tutor.gamification import award_xp, get_level_info
        award_xp(1000, "test")
        info = get_level_info()
        assert info["level"] == "Mestre"
        assert info["next_level"] is None

    def test_level_progress_percent(self, tmp_db):
        from app.tutor.gamification import award_xp, get_level_info
        award_xp(150, "test")
        info = get_level_info()
        assert info["level"] == "Estudante"
        assert 0 < info["progress_percent"] < 100


class TestLeaderboard:
    def test_leaderboard_empty(self, tmp_db):
        from app.tutor.gamification import leaderboard
        result = leaderboard()
        assert result["level"] == "Iniciante"
        assert result["total_xp"] == 0
        assert result["recent_activity"] == []

    def test_leaderboard_with_data(self, tmp_db):
        from app.tutor.gamification import award_xp, leaderboard
        award_xp(100, "exercise")
        award_xp(50, "flashcard")
        result = leaderboard()
        assert result["total_xp"] == 150
        assert len(result["recent_activity"]) == 2

    def test_leaderboard_weekly_xp(self, tmp_db):
        from app.tutor.gamification import award_xp, leaderboard
        award_xp(100, "exercise")
        result = leaderboard()
        assert result["weekly_xp"] == 100
