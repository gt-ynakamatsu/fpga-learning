"""FastAPI エンドポイントのテスト"""

from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient


def _deltasim_v022_or_later() -> bool:
    """deltasim 0.2.2 以上がインストールされているか確認"""
    if not shutil.which("deltasim"):
        return False
    try:
        from fpga_study.simulator import get_deltasim_version, _version_tuple
        ver = get_deltasim_version()
        return ver is not None and _version_tuple(ver) >= (0, 2, 2)
    except Exception:
        return False


_REQUIRE_DELTASIM_022 = pytest.mark.skipif(
    not _deltasim_v022_or_later(),
    reason="deltasim 0.2.2 以上が必要（版不足時は事前チェック前にバージョンエラーを返す）",
)


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
        """quiz/complete はクライアント送信の score を無視し DB の値を返す"""
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/complete",
            json={"score": 4, "total": 4},  # 無視される
        )
        assert res.status_code == 200
        data = res.json()
        # サーバー側では未回答なので quiz_score=0
        assert data["quiz_score"] == 0


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


class TestQuizServerSideScore:
    """クイズ点数はサーバー側で管理される（クライアント送信値を無視）"""

    def test_quiz_complete_with_fake_score_does_not_complete(self, client):
        """クライアントが score=total を送っても、答えていなければ完了にならない"""
        res = client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/complete",
            json={"score": 4, "total": 4},  # 答えていないのに満点を送る
        )
        assert res.status_code == 200
        prog = res.json()
        # サーバー側の記録（0点）を使うので completed=0
        assert prog["completed"] == 0, (
            "クライアント送信の score=total を信じて completed=1 になってしまいました"
        )
        assert prog["quiz_score"] == 0, (
            f"サーバー側では0点のはずが {prog['quiz_score']} になっています"
        )

    def test_quiz_check_all_correct_auto_saves(self, client):
        """quiz/check で全問正解したとき自動的に完了が記録される"""
        # 全問に正解する
        for q_id, ans_idx in [("q1", 1), ("q2", 2), ("q3", 1), ("q4", 2)]:
            res = client.post(
                "/api/chapters/chapter01/lessons/lesson01/quiz/check",
                json={"question_id": q_id, "answer_index": ans_idx},
            )
            assert res.status_code == 200

        # 練習問題も全問正解しないと completed=1 にはならない
        # （進捗のクイズスコアが更新されているか確認）
        prog = client.get("/api/progress/chapter01/lesson01").json()
        assert prog["quiz_score"] > 0, "quiz/check 後にスコアが記録されていません"


class TestQuizAttemptIsolation:
    """§11.14: 1回の挑戦で全問正解のみ満点（attempt_id 管理）"""

    _CORRECT = [("q1", 1), ("q2", 2), ("q3", 1), ("q4", 2)]
    _URL = "/api/chapters/chapter01/lessons/lesson01/quiz/check"
    _RESET_URL = "/api/chapters/chapter01/lessons/lesson01/quiz/reset"

    def test_cumulative_across_attempts_does_not_complete(self, client):
        """attempt_id が変わると前回の正解はリセットされる（累積では満点にならない）"""
        # 1回目の attempt: q1 と q2 だけ正解
        for qid, idx in self._CORRECT[:2]:
            client.post(self._URL, json={"question_id": qid, "answer_index": idx,
                                         "attempt_id": "attempt-A"})

        # 2回目の attempt: q3 と q4 だけ正解
        for qid, idx in self._CORRECT[2:]:
            client.post(self._URL, json={"question_id": qid, "answer_index": idx,
                                         "attempt_id": "attempt-B"})

        # attempt-B では q3+q4 しか答えていないので quiz_score < 4
        prog = client.get("/api/progress/chapter01/lesson01").json()
        assert prog["quiz_score"] < 4, (
            f"attempt をまたいだ累積で満点（{prog['quiz_score']}/4）になりました"
        )

    def test_single_complete_attempt_registers_full_score(self, client):
        """1回の attempt で全問正解 → スコアが全問分記録される"""
        attempt_id = "attempt-single"
        for qid, idx in self._CORRECT:
            res = client.post(self._URL, json={"question_id": qid, "answer_index": idx,
                                               "attempt_id": attempt_id})
            assert res.status_code == 200

        prog = client.get("/api/progress/chapter01/lesson01").json()
        assert prog["quiz_score"] == 4, (
            f"1回の attempt で全問正解したのにスコアが {prog['quiz_score']}/4 です"
        )

    def test_reset_clears_previous_attempt(self, client):
        """quiz/reset 後に新 attempt_id で始めれば前回の正解は引き継がれない"""
        # まず1問答える
        client.post(self._URL, json={"question_id": "q1", "answer_index": 1,
                                     "attempt_id": "before-reset"})
        # リセット
        client.post(self._RESET_URL, json={})
        # 新しい attempt で q2 だけ答える
        client.post(self._URL, json={"question_id": "q2", "answer_index": 2,
                                     "attempt_id": "after-reset"})

        prog = client.get("/api/progress/chapter01/lesson01").json()
        # q1 の正解は引き継がれず、q2 の 1点のみ
        assert prog["quiz_score"] == 1, (
            f"reset 後に前回の正解が引き継がれました: score={prog['quiz_score']}"
        )

    def test_page_reload_new_attempt_resets_score(self, client):
        """同じ問題を別 attempt で答えると前回の正解がリセットされる"""
        # attempt-1 で全問正解
        for qid, idx in self._CORRECT:
            client.post(self._URL, json={"question_id": qid, "answer_index": idx,
                                         "attempt_id": "reload-1"})
        # ページ「再読み込み」= 新 attempt_id、今回は q1 だけ正解
        client.post(self._URL, json={"question_id": "q1", "answer_index": 1,
                                     "attempt_id": "reload-2"})

        prog = client.get("/api/progress/chapter01/lesson01").json()
        # reload-2 では q1 の 1点のみ（reload-1 の正解は消えた）
        assert prog["quiz_score"] == 1, (
            f"ページ再読み込み後に前回の正解が残っています: score={prog['quiz_score']}"
        )

    def test_no_attempt_id_does_not_accumulate(self, client):
        """attempt_id なしで全問正解しても累積 4/4 にならない（各問が別 attempt 扱い）"""
        for qid, idx in self._CORRECT:
            client.post(self._URL, json={"question_id": qid, "answer_index": idx})

        prog = client.get("/api/progress/chapter01/lesson01").json()
        # attempt_id なし = 各問が auto-UUID で別 attempt → 累積しない
        assert prog["quiz_score"] < 4, (
            f"attempt_id なしで累積 {prog['quiz_score']}/4 になりました"
        )


class TestNoTmpPaths:
    """API レスポンスに /tmp パスが含まれないこと"""

    def test_syntax_error_response_has_no_tmp_path(self, client):
        """文法エラーの採点レスポンスに /tmp が含まれないこと"""
        import json as _json
        bad_code = "module and_gate(input logic a, b, output logic y);\n    assign y = a & ;\nendmodule\n"
        res = client.post(
            "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
            json={"code": bad_code},
        )
        assert res.status_code == 200
        raw = _json.dumps(res.json())
        assert "/tmp" not in raw, (
            f"API レスポンスに /tmp が含まれています:\n{raw[:500]}"
        )


class TestDraftEndpoints404:
    """show_drafts なし起動時に draft のコンテンツが 404 を返すこと"""

    def test_get_chapter_draft_returns_404(self, tmp_db):
        """GET /api/chapters/{draft_chapter} が 404（monkeypatch で draft 章を作成）"""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from fpga_study.server import create_app

        # show_drafts=False のサーバー
        app = create_app(db_path=tmp_db, show_drafts=False)
        client = TestClient(app)

        # load_chapter を mock して draft 章を返す
        draft_ch = {"id": "chapter03", "title": "test", "order": 3,
                    "status": "draft", "lessons": []}
        with patch("fpga_study.server.load_chapter", return_value=draft_ch):
            res = client.get("/api/chapters/chapter03")
        assert res.status_code == 404, f"draft 章が 404 になっていません: {res.status_code}"

    def test_get_chapter_reviewed_returns_200(self, client):
        """GET /api/chapters/{reviewed_chapter} は 200"""
        # chapter01 は reviewed
        res = client.get("/api/chapters/chapter01")
        assert res.status_code == 200


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
        """quiz/complete はクライアント送信スコアを無視するので進捗に記録されない"""
        client.post(
            "/api/chapters/chapter01/lessons/lesson01/quiz/complete",
            json={"score": 4, "total": 4},  # 無視される
        )
        res = client.get("/api/progress")
        assert res.status_code == 200
        data = res.json()
        # サーバー側は未回答なので score=0
        quiz_scored = [p for p in data["progress"] if p["quiz_score"] > 0]
        assert len(quiz_scored) == 0

    def test_homepage_returns_html(self, client):  # noqa: E301
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "FPGAお勉強アプリ" in res.text


class TestHdlPreflightChecks:
    """採点前チェック: テンプレート未編集・モジュール名・endmodule
    
    deltasim 0.2.2 未満・なし環境では、事前チェック前にバージョンエラーが返るため SKIP。
    """

    @_REQUIRE_DELTASIM_022
    def test_template_not_modified_gets_special_message(self, client):
        """テンプレートそのまま提出 → §11.24 専用メッセージ"""
        from fpga_study.content.loader import load_exercise
        ex = load_exercise("chapter06", "lesson01")
        template = (ex or {}).get("template", "")
        if not template:
            pytest.skip("テンプレートが exercise.yaml に無い")
        res = client.post(
            "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
            json={"code": template},
        )
        assert res.status_code == 200
        data = res.json()
        msg = data.get("user_message", "")
        assert "まだ回路が書かれていない" in msg or "途中で終わっています" in msg, (
            f"テンプレート未編集の専用メッセージが出ません: {msg!r}"
        )

    @_REQUIRE_DELTASIM_022
    def test_wrong_module_name_shows_correct_name(self, client):
        """モジュール名間違い → 「{top_name} にしてください」（spec/top: は出さない）"""
        code = "module wrong_name(input logic a, b, output logic y);\n    assign y = a & b;\nendmodule\n"
        res = client.post(
            "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
            json={"code": code},
        )
        assert res.status_code == 200
        data = res.json()
        msg = data.get("user_message", "")
        # 正しいモジュール名を案内すること
        assert "and_gate" in msg, f"正しいモジュール名が案内されません: {msg!r}"
        # spec / top: は出さないこと
        assert "spec" not in msg and "top:" not in msg, (
            f"spec/top: が学習者に見えています: {msg!r}"
        )

    @_REQUIRE_DELTASIM_022
    def test_endmodule_missing_no_code_name_in_user_message(self, client):
        """endmodule 抜け → E_NO_ENDMODULE コード名が user_message に出ない"""
        code = "module and_gate(input logic a, b, output logic y);\n    assign y = a & b;\n"
        res = client.post(
            "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
            json={"code": code},
        )
        data = res.json()
        msg = data.get("user_message", "")
        assert "E_NO_ENDMODULE" not in msg
        assert "書き方にまちがいがあります" in msg
