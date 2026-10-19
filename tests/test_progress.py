"""進捗保存・バッジ付与のテスト"""

from __future__ import annotations

from pathlib import Path

import pytest

from fpga_study.progress import (
    get_all_progress,
    get_badges,
    get_lesson_progress,
    init_db,
    save_puzzle_result,
    save_quiz_result,
)


class TestProgressInit:
    def test_init_db_creates_tables(self, tmp_db):
        import sqlite3
        conn = sqlite3.connect(str(tmp_db))
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "lesson_progress" in tables
        assert "badges" in tables

    def test_get_lesson_progress_default(self, tmp_db):
        prog = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert prog["completed"] == 0
        assert prog["quiz_score"] == 0


class TestQuizProgress:
    def test_save_quiz_result_full_score(self, tmp_db):
        result = save_quiz_result("chapter01", "lesson01", 4, 4, db_path=tmp_db)
        assert result["completed"] == 1
        assert result["quiz_score"] == 4
        assert result["completed_at"] is not None

    def test_save_quiz_result_partial(self, tmp_db):
        result = save_quiz_result("chapter01", "lesson01", 2, 4, db_path=tmp_db)
        assert result["completed"] == 0
        assert result["quiz_score"] == 2

    def test_save_quiz_result_better_score_updates(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 2, 4, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson01", 4, 4, db_path=tmp_db)
        result = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert result["quiz_score"] == 4
        assert result["completed"] == 1

    def test_save_quiz_result_worse_score_no_update(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 4, 4, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson01", 2, 4, db_path=tmp_db)
        result = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert result["quiz_score"] == 4

    def test_get_all_progress(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 3, 3, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson02", 2, 4, db_path=tmp_db)
        all_prog = get_all_progress(tmp_db)
        assert len(all_prog) == 2


class TestPuzzleProgress:
    def test_save_puzzle_result_pass(self, tmp_db):
        result = save_puzzle_result("chapter02", "lesson03", passed=True, db_path=tmp_db)
        assert result["puzzle_completed"] == 1
        # パズル合格だけでは完了にならない（仕様未定のため条件外）
        assert result["completed"] == 0

    def test_save_puzzle_result_fail(self, tmp_db):
        result = save_puzzle_result("chapter02", "lesson03", passed=False, db_path=tmp_db)
        assert result["puzzle_completed"] == 0
        assert result["completed"] == 0


class TestCompletionConditions:
    """完了条件の組み合わせテスト"""

    def test_quiz_only_not_complete_without_exercises(self, tmp_db):
        """クイズ満点だけでは練習問題がある場合に完了しない"""
        from fpga_study.progress import save_quiz_result, get_lesson_progress
        save_quiz_result("chapter01", "lesson01", 4, 4,
                         all_problem_ids=["p1", "p2", "p3"], has_hdl=False, db_path=tmp_db)
        prog = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert prog["completed"] == 0, "練習問題が未完了なのに completed になっています"

    def test_exercise_only_not_complete_without_quiz(self, tmp_db):
        """練習問題全完了だけではクイズがある場合に完了しない"""
        from fpga_study.progress import save_practice_problem_result, get_lesson_progress
        for pid in ["p1", "p2"]:
            save_practice_problem_result("chapter01", "lesson01", pid,
                                         ["p1", "p2"], has_hdl=False,
                                         quiz_total=4, db_path=tmp_db)
        prog = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert prog["completed"] == 0, "クイズが未完了なのに completed になっています"

    def test_all_conditions_complete(self, tmp_db):
        """練習問題全完了 + クイズ満点 = 完了"""
        from fpga_study.progress import save_practice_problem_result, save_quiz_result, get_lesson_progress
        for pid in ["p1", "p2"]:
            save_practice_problem_result("chapter01", "lesson01", pid,
                                         ["p1", "p2"], has_hdl=False,
                                         quiz_total=4, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson01", 4, 4,
                         all_problem_ids=["p1", "p2"], has_hdl=False, db_path=tmp_db)
        prog = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert prog["completed"] == 1

    def test_hdl_required_not_complete_without_hdl_pass(self, tmp_db):
        """HDL演習がある場合、クイズ+練習完了だけでは完了しない"""
        from fpga_study.progress import save_quiz_result, save_practice_problem_result, get_lesson_progress
        save_practice_problem_result("chapter06", "lesson03", "p1",
                                     ["p1"], has_hdl=True, quiz_total=2, db_path=tmp_db)
        save_quiz_result("chapter06", "lesson03", 2, 2,
                         all_problem_ids=["p1"], has_hdl=True, db_path=tmp_db)
        prog = get_lesson_progress("chapter06", "lesson03", tmp_db)
        assert prog["completed"] == 0, "HDL未合格なのに completed になっています"

    def test_hdl_pass_completes_lesson(self, tmp_db):
        """HDL演習も合格すると完了"""
        from fpga_study.progress import save_quiz_result, save_practice_problem_result, save_hdl_result, get_lesson_progress
        save_practice_problem_result("chapter06", "lesson03", "p1",
                                     ["p1"], has_hdl=True, quiz_total=2, db_path=tmp_db)
        save_quiz_result("chapter06", "lesson03", 2, 2,
                         all_problem_ids=["p1"], has_hdl=True, db_path=tmp_db)
        save_hdl_result("chapter06", "lesson03",
                        all_problem_ids=["p1"], quiz_total=2, db_path=tmp_db)
        prog = get_lesson_progress("chapter06", "lesson03", tmp_db)
        assert prog["completed"] == 1

    def test_partial_exercise_not_complete(self, tmp_db):
        """練習問題の一部だけ合格しても完了しない"""
        from fpga_study.progress import save_practice_problem_result, save_quiz_result, get_lesson_progress
        save_practice_problem_result("chapter01", "lesson01", "p1",
                                     ["p1", "p2", "p3"], has_hdl=False,
                                     quiz_total=4, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson01", 4, 4,
                         all_problem_ids=["p1", "p2", "p3"], has_hdl=False, db_path=tmp_db)
        prog = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert prog["completed"] == 0, "p2/p3 が未完了なのに completed になっています"


class TestPuzzleCompletion:
    """パズル合格だけでは完了しないことを確認"""

    def test_puzzle_alone_does_not_complete(self, tmp_db):
        """パズル合格だけでは completed=0（仕様未定のためパズルは完了条件に含まない）"""
        from fpga_study.progress import save_puzzle_result, get_lesson_progress
        result = save_puzzle_result("chapter02", "lesson03", passed=True, db_path=tmp_db)
        assert result["puzzle_completed"] == 1
        assert result["completed"] == 0, (
            "パズルだけで completed=1 になっています。"
            "パズルは完了条件に含まれません（仕様未定）。"
        )

    def test_puzzle_plus_quiz_without_exercises_not_complete(self, tmp_db):
        """パズル + クイズ満点だけでは、練習問題がある場合に完了しない"""
        from fpga_study.progress import save_puzzle_result, save_quiz_result, get_lesson_progress
        save_puzzle_result("chapter02", "lesson03", passed=True, db_path=tmp_db)
        save_quiz_result("chapter02", "lesson03", 3, 3,
                         all_problem_ids=["p1", "p2", "p3"], db_path=tmp_db)
        prog = get_lesson_progress("chapter02", "lesson03", tmp_db)
        assert prog["completed"] == 0


class TestBadges:
    def test_first_lesson_badge(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 4, 4, db_path=tmp_db)
        badges = get_badges(tmp_db)
        badge_ids = {b["badge_id"] for b in badges}
        assert "first_lesson" in badge_ids

    def test_three_lessons_badge(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 3, 3, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson02", 4, 4, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson03", 3, 3, db_path=tmp_db)
        badges = get_badges(tmp_db)
        badge_ids = {b["badge_id"] for b in badges}
        assert "three_lessons" in badge_ids

    def test_no_duplicate_badges(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 4, 4, db_path=tmp_db)
        save_quiz_result("chapter01", "lesson01", 4, 4, db_path=tmp_db)
        badges = get_badges(tmp_db)
        first_lesson_badges = [b for b in badges if b["badge_id"] == "first_lesson"]
        assert len(first_lesson_badges) == 1
