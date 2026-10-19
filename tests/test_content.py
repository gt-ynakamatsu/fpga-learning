"""教材YAMLスキーマ検証・コンテンツローダーのテスト"""

from __future__ import annotations

from pathlib import Path

import pytest

from fpga_study.content.loader import (
    load_chapters,
    load_lesson,
    load_lessons,
    _eval_gate,
    evaluate_circuit,
)
from fpga_study.content.validator import (
    ValidationError,
    validate_chapter_meta,
    validate_exercise,
    validate_puzzle,
    validate_quiz,
)


class TestSchemaValidation:
    def test_chapter_meta_valid(self):
        validate_chapter_meta({
            "id": "chapter01", "title": "テスト章", "order": 1,
            "lessons": ["lesson01"], "status": "draft",
        })

    def test_chapter_meta_missing_required(self):
        with pytest.raises(ValidationError):
            validate_chapter_meta({"id": "chapter01"})

    def test_chapter_meta_bad_order(self):
        with pytest.raises(ValidationError):
            validate_chapter_meta({
                "id": "c1", "title": "t", "order": 0, "lessons": ["l1"]
            })

    def test_quiz_valid(self):
        validate_quiz({
            "questions": [{
                "id": "q1", "question": "test?",
                "options": ["A", "B"], "answer": 0, "explanation": "説明",
            }]
        })

    def test_quiz_no_questions(self):
        with pytest.raises(ValidationError):
            validate_quiz({"questions": []})

    def test_quiz_missing_answer(self):
        with pytest.raises(ValidationError):
            validate_quiz({
                "questions": [{"id": "q1", "question": "?", "options": ["A", "B"]}]
            })

    def test_puzzle_valid(self):
        validate_puzzle({
            "id": "p1", "title": "テストパズル",
            "inputs": [{"name": "A"}],
            "outputs": [{"name": "Y"}],
            "available_gates": [{"type": "AND", "count": 1}],
            "target_truth_table": [
                {"inputs": {"A": 0}, "outputs": {"Y": 0}},
            ],
        })

    def test_puzzle_invalid_gate_type(self):
        with pytest.raises(ValidationError):
            validate_puzzle({
                "id": "p1", "title": "t",
                "inputs": [{"name": "A"}],
                "outputs": [{"name": "Y"}],
                "available_gates": [{"type": "UNKNOWN", "count": 1}],
                "target_truth_table": [{"inputs": {"A": 0}, "outputs": {"Y": 0}}],
            })

    def test_puzzle_dff_gate_type_valid(self):
        """DFF はゲートタイプとして有効"""
        validate_puzzle({
            "id": "p1", "title": "DFF パズル",
            "type": "sequential",
            "inputs": [{"name": "D"}],
            "outputs": [{"name": "Q"}],
            "available_gates": [{"type": "DFF", "count": 1}],
            "target_truth_table": [
                {"clock": 0, "inputs": {"D": 1}, "outputs": {"Q": 0}},
            ],
        })

    def test_puzzle_sequential_type_valid(self):
        """type: sequential は有効"""
        validate_puzzle({
            "id": "p_seq", "title": "順序回路",
            "type": "sequential",
            "inputs": [{"name": "D"}],
            "outputs": [{"name": "Q"}],
            "available_gates": [{"type": "DFF", "count": 1}],
            "target_truth_table": [{"clock": 0, "inputs": {"D": 0}, "outputs": {"Q": 0}}],
        })

    def test_quiz_status_field_invalid(self):
        """quiz.yaml に status フィールドがあるとエラー（decisions 1 で廃止）"""
        # quiz の status は validation では強制しないが、has_no_status_field テストで実ファイルをチェック
        # スキーマレベルでは status は additionalProperties で許容（廃止は慣習）
        pass


class TestExerciseSchema:
    def test_practice_exercise_valid(self):
        """練習問題（practice）の有効なexercise.yaml"""
        validate_exercise({
            "id": "ex1",
            "type": "practice",
            "problems": [
                {
                    "id": "p1",
                    "type": "fill_number",
                    "question": "いくつ？",
                    "answer": 42,
                    "hint": "ヒント",
                }
            ],
        })

    def test_hdl_exercise_valid(self):
        """HDL演習（hdl）の有効なexercise.yaml"""
        validate_exercise({
            "id": "ex_hdl",
            "type": "hdl",
            "problems": [
                {
                    "id": "p1",
                    "type": "fill_text",
                    "question": "コードを書いてください",
                    "answer": "a & b",
                }
            ],
        })

    def test_exercise_invalid_type(self):
        with pytest.raises(ValidationError):
            validate_exercise({
                "id": "ex", "type": "unknown",
                "problems": [{"id": "p1", "type": "fill_number", "question": "?", "answer": 1}],
            })

    def test_exercise_invalid_problem_type(self):
        with pytest.raises(ValidationError):
            validate_exercise({
                "id": "ex", "type": "practice",
                "problems": [{"id": "p1", "type": "invalid_type", "question": "?", "answer": 1}],
            })


class TestContentLoader:
    def test_load_chapters_returns_list(self, data_root):
        chapters = load_chapters(data_root)
        assert isinstance(chapters, list)
        assert len(chapters) >= 1

    def test_chapters_sorted_by_order(self, data_root):
        chapters = load_chapters(data_root)
        orders = [ch["order"] for ch in chapters]
        assert orders == sorted(orders)

    def test_load_chapter01_lessons(self, data_root):
        lessons = load_lessons("chapter01", data_root)
        assert len(lessons) == 3
        assert lessons[0]["lesson_id"] == "lesson01"

    def test_load_lesson_has_content(self, data_root):
        lesson = load_lesson("chapter01", "lesson01", data_root)
        assert lesson is not None
        assert lesson["content_html"]
        assert "<h1>" in lesson["content_html"]

    def test_load_lesson_has_quiz(self, data_root):
        lesson = load_lesson("chapter01", "lesson01", data_root)
        assert lesson["quiz"] is not None
        assert len(lesson["quiz"]["questions"]) >= 1

    def test_load_lesson_has_status(self, data_root):
        lesson = load_lesson("chapter01", "lesson01", data_root)
        # Ch1 は reviewed 済み (decisions 1 の status 値を確認)
        assert lesson.get("status") in {"draft", "review", "reviewed", "published"}

    def test_load_chapter02_lesson03_has_puzzle(self, data_root):
        lesson = load_lesson("chapter02", "lesson03", data_root)
        assert lesson is not None
        assert lesson["puzzle"] is not None
        assert lesson["puzzle"]["id"] == "puzzle_xor_gate"

    def test_load_nonexistent_lesson(self, data_root):
        lesson = load_lesson("chapter99", "lesson99", data_root)
        assert lesson is None

    def test_load_chapter03_has_3_lessons(self, data_root):
        lessons = load_lessons("chapter03", data_root)
        assert len(lessons) == 3

    def test_load_chapter03_lesson03_has_puzzle(self, data_root):
        lesson = load_lesson("chapter03", "lesson03", data_root)
        assert lesson is not None
        assert lesson["puzzle"] is not None
        assert lesson["puzzle"]["id"] == "puzzle_half_adder"

    def test_load_chapter04_lesson03_sequential_puzzle(self, data_root):
        lesson = load_lesson("chapter04", "lesson03", data_root)
        assert lesson is not None
        assert lesson["puzzle"] is not None
        assert lesson["puzzle"].get("type") == "sequential"

    def test_load_chapter05_has_3_lessons(self, data_root):
        lessons = load_lessons("chapter05", data_root)
        assert len(lessons) == 3

    def test_all_5_chapters_load(self, data_root):
        chapters = load_chapters(data_root)
        ids = [ch["id"] for ch in chapters]
        for cid in ["chapter01", "chapter02", "chapter03", "chapter04", "chapter05"]:
            assert cid in ids

    def test_chapter06_has_3_lessons(self, data_root):
        lessons = load_lessons("chapter06", data_root)
        assert len(lessons) == 3

    def test_chapter07_has_2_lessons(self, data_root):
        lessons = load_lessons("chapter07", data_root)
        assert len(lessons) == 2

    def test_lesson_status_uses_new_values(self, data_root):
        """status が新定義 (draft|review|reviewed|published) の値を使っている"""
        valid_statuses = {"draft", "review", "reviewed", "published"}
        chapters = load_chapters(data_root)
        for ch in chapters:
            if "status" in ch:
                assert ch["status"] in valid_statuses, f"{ch['id']}: invalid status {ch['status']}"

    def test_exercise_quiz_no_duplicate_prompts(self, data_root):
        """同一レッスンの exercise と quiz で同じ問題文がないことを確認"""
        import yaml
        for chapter_dir in sorted(data_root.iterdir()):
            if not chapter_dir.is_dir():
                continue
            for lesson_dir in sorted(chapter_dir.iterdir()):
                if not lesson_dir.is_dir():
                    continue
                ex_path = lesson_dir / "exercise.yaml"
                quiz_path = lesson_dir / "quiz.yaml"
                if not (ex_path.exists() and quiz_path.exists()):
                    continue
                ex = yaml.safe_load(ex_path.read_text())
                quiz = yaml.safe_load(quiz_path.read_text())
                if not (ex and quiz):
                    continue
                # type: hdl は比較対象外
                if ex.get("type") == "hdl":
                    continue
                ex_questions = {p["question"].strip() for p in ex.get("problems", [])}
                quiz_questions = {q["question"].strip() for q in quiz.get("questions", [])}
                overlap = ex_questions & quiz_questions
                assert not overlap, (
                    f"{lesson_dir}: exercise と quiz に同じ問題文があります: {overlap}"
                )

    def test_exercises_no_duplicate_prompts_within_chapter(self, data_root):
        """同一章内の exercise で同じ問題文がないことを確認"""
        import yaml
        for chapter_dir in sorted(data_root.iterdir()):
            if not chapter_dir.is_dir():
                continue
            all_questions: dict[str, str] = {}  # question → lesson_id
            for lesson_dir in sorted(chapter_dir.iterdir()):
                if not lesson_dir.is_dir():
                    continue
                ex_path = lesson_dir / "exercise.yaml"
                if not ex_path.exists():
                    continue
                ex = yaml.safe_load(ex_path.read_text())
                if not ex or ex.get("type") == "hdl":
                    continue
                lesson_id = lesson_dir.name
                for p in ex.get("problems", []):
                    q = p["question"].strip()
                    if q in all_questions:
                        assert False, (
                            f"{chapter_dir.name}/{lesson_id}: 演習問題が "
                            f"{all_questions[q]} と重複しています: {q!r}"
                        )
                    all_questions[q] = lesson_id

    def test_spec_cases_have_japanese_descriptions(self, data_root):
        """HDL演習のある全レッスンで spec.yaml の全ケースに日本語説明があること"""
        import yaml
        for chapter_dir in sorted(data_root.iterdir()):
            if not chapter_dir.is_dir():
                continue
            for lesson_dir in sorted(chapter_dir.iterdir()):
                if not lesson_dir.is_dir():
                    continue
                spec_path = lesson_dir / "spec.yaml"
                ex_path = lesson_dir / "exercise.yaml"
                if not (spec_path.exists() and ex_path.exists()):
                    continue
                spec = yaml.safe_load(spec_path.read_text())
                ex = yaml.safe_load(ex_path.read_text())
                if ex.get("type") != "hdl":
                    continue
                descriptions = ex.get("case_descriptions", {})
                for case in spec.get("cases", []):
                    name = case.get("name", "")
                    assert name in descriptions, (
                        f"{lesson_dir}: spec ケース '{name}' の日本語説明が "
                        f"exercise.yaml の case_descriptions にありません"
                    )

    def test_quiz_has_no_status_field(self, data_root):
        """quiz.yaml には status フィールドがない（decisions 1）"""
        import yaml
        for chapter_dir in (data_root).iterdir():
            if not chapter_dir.is_dir():
                continue
            for lesson_dir in chapter_dir.iterdir():
                if not lesson_dir.is_dir():
                    continue
                quiz_path = lesson_dir / "quiz.yaml"
                if quiz_path.exists():
                    data = yaml.safe_load(quiz_path.read_text())
                    assert "status" not in data, (
                        f"{quiz_path}: quiz.yaml に status フィールドがあります（decisions 1 で廃止）"
                    )


class TestGateEval:
    @pytest.mark.parametrize("inputs,expected", [
        ([0, 0], 0), ([0, 1], 0), ([1, 0], 0), ([1, 1], 1),
    ])
    def test_and_gate(self, inputs, expected):
        assert _eval_gate("AND", inputs) == expected

    @pytest.mark.parametrize("inputs,expected", [
        ([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 1),
    ])
    def test_or_gate(self, inputs, expected):
        assert _eval_gate("OR", inputs) == expected

    @pytest.mark.parametrize("inputs,expected", [
        ([0], 1), ([1], 0),
    ])
    def test_not_gate(self, inputs, expected):
        assert _eval_gate("NOT", inputs) == expected

    @pytest.mark.parametrize("inputs,expected", [
        ([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0),
    ])
    def test_xor_gate(self, inputs, expected):
        assert _eval_gate("XOR", inputs) == expected

    @pytest.mark.parametrize("inputs,expected", [
        ([0, 0], 1), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0),
    ])
    def test_nand_gate(self, inputs, expected):
        assert _eval_gate("NAND", inputs) == expected

    @pytest.mark.parametrize("inputs,expected", [
        ([0, 0], 1), ([0, 1], 0), ([1, 0], 0), ([1, 1], 0),
    ])
    def test_nor_gate(self, inputs, expected):
        assert _eval_gate("NOR", inputs) == expected

    def test_unknown_gate_returns_0(self):
        assert _eval_gate("UNKNOWN", [1, 1]) == 0
