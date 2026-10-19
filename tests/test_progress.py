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
        result = save_quiz_result("chapter01", "lesson01", 4, 4, tmp_db)
        assert result["completed"] == 1
        assert result["quiz_score"] == 4
        assert result["completed_at"] is not None

    def test_save_quiz_result_partial(self, tmp_db):
        result = save_quiz_result("chapter01", "lesson01", 2, 4, tmp_db)
        assert result["completed"] == 0
        assert result["quiz_score"] == 2

    def test_save_quiz_result_better_score_updates(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 2, 4, tmp_db)
        save_quiz_result("chapter01", "lesson01", 4, 4, tmp_db)
        result = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert result["quiz_score"] == 4
        assert result["completed"] == 1

    def test_save_quiz_result_worse_score_no_update(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 4, 4, tmp_db)
        save_quiz_result("chapter01", "lesson01", 2, 4, tmp_db)
        result = get_lesson_progress("chapter01", "lesson01", tmp_db)
        assert result["quiz_score"] == 4

    def test_get_all_progress(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 3, 3, tmp_db)
        save_quiz_result("chapter01", "lesson02", 2, 4, tmp_db)
        all_prog = get_all_progress(tmp_db)
        assert len(all_prog) == 2


class TestPuzzleProgress:
    def test_save_puzzle_result_pass(self, tmp_db):
        result = save_puzzle_result("chapter02", "lesson03", passed=True, db_path=tmp_db)
        assert result["puzzle_completed"] == 1
        assert result["completed"] == 1

    def test_save_puzzle_result_fail(self, tmp_db):
        result = save_puzzle_result("chapter02", "lesson03", passed=False, db_path=tmp_db)
        assert result["puzzle_completed"] == 0
        assert result["completed"] == 0


class TestBadges:
    def test_first_lesson_badge(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 4, 4, tmp_db)
        badges = get_badges(tmp_db)
        badge_ids = {b["badge_id"] for b in badges}
        assert "first_lesson" in badge_ids

    def test_three_lessons_badge(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 3, 3, tmp_db)
        save_quiz_result("chapter01", "lesson02", 4, 4, tmp_db)
        save_quiz_result("chapter01", "lesson03", 3, 3, tmp_db)
        badges = get_badges(tmp_db)
        badge_ids = {b["badge_id"] for b in badges}
        assert "three_lessons" in badge_ids

    def test_no_duplicate_badges(self, tmp_db):
        save_quiz_result("chapter01", "lesson01", 4, 4, tmp_db)
        save_quiz_result("chapter01", "lesson01", 4, 4, tmp_db)
        badges = get_badges(tmp_db)
        first_lesson_badges = [b for b in badges if b["badge_id"] == "first_lesson"]
        assert len(first_lesson_badges) == 1
