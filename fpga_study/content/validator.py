"""教材YAMLのスキーマ検証"""

from __future__ import annotations

from typing import Any

import jsonschema

# decisions 1: status の値は draft | review | reviewed | published
# review = 確認依頼中、reviewed = 仕様考案係が確認済み、published = リリース組み込み済み
STATUS_ENUM = ["draft", "review", "reviewed", "published"]

CHAPTER_META_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "title", "order", "lessons"],
    "additionalProperties": True,
    "properties": {
        "id":          {"type": "string"},
        "title":       {"type": "string"},
        "description": {"type": "string"},
        "order":       {"type": "integer", "minimum": 1},
        "status":      {"type": "string", "enum": STATUS_ENUM},
        "lessons": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
    },
}

LESSON_META_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "title"],
    "additionalProperties": True,
    "properties": {
        "id":              {"type": "string"},
        "title":           {"type": "string"},
        "description":     {"type": "string"},
        "estimated_min":   {"type": "integer", "minimum": 1},
        # decisions 1: status は meta.yaml のみ。quiz/puzzle には持たせない
        "status":          {"type": "string", "enum": STATUS_ENUM},
        # decisions 2: has_puzzle / has_exercise / has_hdl_exercise は省略時 false の任意項目
        # has_exercise    = exercise.yaml に通常の練習問題がある（fill_number/fill_text 等）
        # has_hdl_exercise = HDL演習（exercise.yaml の type: hdl）のみ → has_exercise は false
        # has_puzzle      = puzzle.yaml がある（回路パズル）
        "has_puzzle":       {"type": "boolean"},
        "has_exercise":     {"type": "boolean"},
        "has_hdl_exercise": {"type": "boolean"},
    },
}

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions"],
    "additionalProperties": True,
    "properties": {
        # decisions 1: quiz.yaml の status は廃止（meta.yaml で管理）
        "questions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "question", "options", "answer"],
                "additionalProperties": True,
                "properties": {
                    "id":          {"type": "string"},
                    "question":    {"type": "string"},
                    "options":     {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                    "answer":      {"type": "integer", "minimum": 0},
                    "explanation": {"type": "string"},
                    # decisions 7: 誤答ごとの解説（任意）
                    "option_explanations": {
                        "type": "array",
                        "items": {"type": ["string", "null"]},
                    },
                },
            },
        },
    },
}

EXERCISE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "type", "problems"],
    "additionalProperties": True,
    "properties": {
        "id":   {"type": "string"},
        "type": {"type": "string", "enum": ["practice", "hdl"]},
        "problems": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "type", "question", "answer"],
                "additionalProperties": True,
                "properties": {
                    "id":         {"type": "string"},
                    "type":       {"type": "string", "enum": ["fill_number", "fill_text", "sort_items"]},
                    "question":   {"type": "string"},
                    "answer":     {},
                    "hint":       {"type": "string"},
                    "wrong_hint": {"type": "string"},
                },
            },
        },
    },
}

PUZZLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "title", "inputs", "outputs", "available_gates", "target_truth_table"],
    "additionalProperties": True,
    "properties": {
        "id":          {"type": "string"},
        "title":       {"type": "string"},
        "description": {"type": "string"},
        # decisions 1: puzzle.yaml の status は廃止
        "inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
            "minItems": 1,
        },
        "outputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
            "minItems": 1,
        },
        "type": {
            "type": "string",
            "enum": ["combinational", "sequential"],
        },
        "available_gates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "count"],
                "properties": {
                    "type":  {
                        "type": "string",
                        "enum": ["AND", "OR", "NOT", "XOR", "NAND", "NOR", "DFF"],
                    },
                    "count": {"type": "integer", "minimum": 1},
                },
            },
        },
        "target_truth_table": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["inputs", "outputs"],
                "additionalProperties": True,
                "properties": {
                    "clock":   {"type": "integer", "minimum": 0},
                    "inputs":  {"type": "object"},
                    "outputs": {"type": "object"},
                },
            },
        },
    },
}


class ValidationError(Exception):
    """スキーマ検証エラー"""


def validate_chapter_meta(data: dict) -> None:
    """章メタデータを検証する。エラー時は ValidationError を送出する"""
    _validate(data, CHAPTER_META_SCHEMA, "章メタデータ")


def validate_lesson_meta(data: dict) -> None:
    """レッスンメタデータを検証する"""
    _validate(data, LESSON_META_SCHEMA, "レッスンメタデータ")


def validate_quiz(data: dict) -> None:
    """クイズYAMLを検証する"""
    _validate(data, QUIZ_SCHEMA, "クイズ")


def validate_puzzle(data: dict) -> None:
    """パズルYAMLを検証する"""
    _validate(data, PUZZLE_SCHEMA, "回路パズル")


def validate_exercise(data: dict) -> None:
    """演習YAMLを検証する"""
    _validate(data, EXERCISE_SCHEMA, "演習")


def _validate(data: dict, schema: dict, label: str) -> None:
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        path = " > ".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ValidationError(f"{label}の検証エラー [{path}]: {exc.message}") from exc
