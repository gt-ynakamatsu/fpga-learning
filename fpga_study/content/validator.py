"""教材YAMLのスキーマ検証"""

from __future__ import annotations

from typing import Any

import jsonschema

CHAPTER_META_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "title", "order", "lessons"],
    "additionalProperties": True,
    "properties": {
        "id":          {"type": "string"},
        "title":       {"type": "string"},
        "description": {"type": "string"},
        "order":       {"type": "integer", "minimum": 1},
        "status":      {"type": "string", "enum": ["draft", "review", "published"]},
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
        "id":           {"type": "string"},
        "title":        {"type": "string"},
        "description":  {"type": "string"},
        "estimated_min":{"type": "integer", "minimum": 1},
        "status":       {"type": "string", "enum": ["draft", "review", "published"]},
        "has_puzzle":   {"type": "boolean"},
    },
}

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions"],
    "additionalProperties": True,
    "properties": {
        "status": {"type": "string", "enum": ["draft", "review", "published"]},
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
        "status":      {"type": "string", "enum": ["draft", "review", "published"]},
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
        "available_gates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "count"],
                "properties": {
                    "type":  {"type": "string", "enum": ["AND", "OR", "NOT", "XOR", "NAND", "NOR"]},
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
                "properties": {
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


def _validate(data: dict, schema: dict, label: str) -> None:
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        path = " > ".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ValidationError(f"{label}の検証エラー [{path}]: {exc.message}") from exc
