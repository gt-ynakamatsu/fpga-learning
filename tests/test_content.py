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
        assert lesson.get("status") == "draft"

    def test_load_chapter02_lesson03_has_puzzle(self, data_root):
        lesson = load_lesson("chapter02", "lesson03", data_root)
        assert lesson is not None
        assert lesson["puzzle"] is not None
        assert lesson["puzzle"]["id"] == "puzzle_and_gate"

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
