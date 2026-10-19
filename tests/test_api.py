"""FastAPI エンドポイントのテスト"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestChapterAPI:
    def test_get_chapters(self, client):
        res = client.get("/api/chapters")
        assert res.status_code == 200
        chapters = res.json()
        assert isinstance(chapters, list)
        assert len(chapters) >= 2
        # order でソートされていること
        orders = [ch["order"] for ch in chapters]
        assert orders == sorted(orders)

    def test_get_chapter01(self, client):
        res = client.get("/api/chapters/chapter01")
        assert res.status_code == 200
        ch = res.json()
        assert ch["id"] == "chapter01"
        assert "title" in ch

    def test_get_chapter_not_found(self, client):
        res = client.get("/api/chapters/chapter99")
        assert res.status_code == 404

    def test_get_chapter01_lessons(self, client):
        res = client.get("/api/chapters/chapter01/lessons")
        assert res.status_code == 200
        lessons = res.json()
        assert len(lessons) == 3

    def test_get_lesson(self, client):
        res = client.get("/api/chapters/chapter01/lessons/lesson01")
        assert res.status_code == 200
        lesson = res.json()
        assert "content_html" in lesson
        assert lesson["content_html"]
        assert "quiz" in lesson

    def test_get_lesson_not_found(self, client):
        res = client.get("/api/chapters/chapter01/lessons/lesson99")
        assert res.status_code == 404

    def test_lesson_has_status_field(self, client):
        res = client.get("/api/chapters/chapter01/lessons/lesson01")
        assert res.status_code == 200
        lesson = res.json()
        assert "status" in lesson

    def test_chapter02_lesson03_has_puzzle(self, client):
        res = client.get("/api/chapters/chapter02/lessons/lesson03")
        assert res.status_code == 200
        lesson = res.json()
        assert lesson["puzzle"] is not None
        assert lesson["puzzle"]["id"] == "puzzle_xor_gate"


class TestQuizAPI:
    def test_check_correct_answer(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/check",
            json={"question_id": "q1", "answer_index": 1},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["correct"] is True
        assert "explanation" in data

    def test_check_wrong_answer(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/check",
            json={"question_id": "q1", "answer_index": 0},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["correct"] is False
        assert data["correct_index"] == 1

    def test_check_invalid_question_id(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/check",
            json={"question_id": "q_nonexistent", "answer_index": 0},
        )
        assert res.status_code == 404

    def test_quiz_complete(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/complete",
            json={"score": 4, "total": 4},
        )
        assert res.status_code == 200
        data = res.json()
        # クイズ満点だが練習問題が未完了なので completed=0
        assert data["completed"] == 0
        assert data["quiz_score"] == 4


class TestPuzzleAPI:
    def _make_and_connections(self):
        # Ch02 lesson03 の puzzle は XOR gate に変更済み
        return {
            "connections": [
                {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
                {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
                {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
            ],
            "gate_placements": [{"id": "gate_1", "type": "XOR", "x": 300, "y": 200}],
        }

    def test_puzzle_check_pass(self, client):
        res = client.post(
            "/api/chapters/chapter02/lessons/lesson03/puzzle/check",
            json=self._make_and_connections(),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["passed"] is True

    def test_puzzle_check_fail(self, client):
        res = client.post(
            "/api/chapters/chapter02/lessons/lesson03/puzzle/check",
            json={"connections": [], "gate_placements": []},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["passed"] is False

    def test_puzzle_check_not_found(self, client):
        res = client.post(
            "/api/chapters/chapter99/lessons/lesson99/puzzle/check",
            json={"connections": [], "gate_placements": []},
        )
        assert res.status_code == 404


class TestExerciseAPI:
    def test_exercise_check_correct(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/exercise/check",
            json={"problem_id": "p1", "answer": 8},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["correct"] is True

    def test_exercise_check_wrong(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/exercise/check",
            json={"problem_id": "p1", "answer": 0},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["correct"] is False
        assert data["hint"] is not None or data["wrong_hint"] is not None

    def test_exercise_check_invalid_problem(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/exercise/check",
            json={"problem_id": "nonexistent", "answer": 1},
        )
        assert res.status_code == 422

    def test_exercise_in_lesson_response(self, client):
        res = client.get("/api/chapters/chapter01/lessons/lesson01")
        assert res.status_code == 200
        data = res.json()
        assert "exercise" in data
        assert data["exercise"] is not None
        assert data["exercise"]["type"] == "practice"

    def test_exercise_missing_lesson_returns_none(self, client):
        res = client.get("/api/chapters/chapter02/lessons/lesson03")
        assert res.status_code == 200
        # L3 has puzzle, exercise should be present or None
        data = res.json()
        assert "exercise" in data

    def test_deltasim_status_endpoint(self, client):
        res = client.get("/api/deltasim/status")
        assert res.status_code == 200
        data = res.json()
        assert "available" in data
        assert "version" in data
        assert "min_version" in data

    def test_hdl_grade_missing_exercise(self, client):
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/hdl/grade",
            json={"code": "module test(); endmodule"},
        )
        assert res.status_code == 404

    def test_chapters_hides_drafts_by_default(self, client):
        """デフォルトでは reviewed/published のみ返す"""
        res = client.get("/api/chapters")
        assert res.status_code == 200
        chapters = res.json()
        for ch in chapters:
            assert ch.get("status") in ("reviewed", "published", None), (
                f"draft/review の章が返されました: {ch['id']}: {ch.get('status')}"
            )

    def test_chapters_shows_drafts_with_param(self, client):
        """show_drafts=true で全章を返す"""
        res = client.get("/api/chapters?show_drafts=true")
        assert res.status_code == 200
        chapters = res.json()
        # 全章が返されるはず
        assert len(chapters) >= 5


class TestProgressAPI:
    def test_get_progress_empty(self, client):
        res = client.get("/api/progress")
        assert res.status_code == 200
        data = res.json()
        assert "progress" in data
        assert "badges" in data
        assert isinstance(data["progress"], list)
        assert isinstance(data["badges"], list)

    def test_get_lesson_progress(self, client):
        res = client.get("/api/progress/chapter01/lesson01")
        assert res.status_code == 200
        data = res.json()
        assert "completed" in data

    def test_progress_after_quiz(self, client):
        client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/complete",
            json={"score": 4, "total": 4},
        )
        res = client.get("/api/progress")
        assert res.status_code == 200
        data = res.json()
        # クイズ満点のみでは completed にならない（練習問題が未完了）
        quiz_scored = [p for p in data["progress"] if p["quiz_score"] > 0]
        assert len(quiz_scored) == 1

    def test_homepage_returns_html(self, client):  # noqa: E301
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "FPGAお勉強アプリ" in res.text
