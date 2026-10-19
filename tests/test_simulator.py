"""
deltasim CLI 連携パーサのテスト
docs/api.md §2.2 のサンプルJSONを使って検証する
"""

from __future__ import annotations

import json

import pytest

from fpga_study.simulator import (
    SUPPORTED_SCHEMA_VERSION,
    SimulationResult,
    StubSimulator,
    _parse_deltasim_result,
)


# ── docs/api.md §2.2 のサンプルJSON ──────────────────

SAMPLE_PASS = json.dumps({
    "schema_version": "1",
    "module": "counter",
    "status": "PASS",
    "seed": 42,
    "elapsed_ms": 12.3,
    "cancelled": False,
    "log": [],
    "checks": [
        {
            "name": "count@cycle11[spec]",
            "status": "PASS",
            "signal": "count",
            "cycle": 11,
            "time_ns": 110,
            "expected": "00000001",
            "actual": "00000001",
            "source": "spec",
            "seed": 42,
            "elapsed_ms": 0.5,
            "message": None,
        }
    ],
    "errors": [],
})

SAMPLE_FAIL = json.dumps({
    "schema_version": "1",
    "module": "counter",
    "status": "FAIL",
    "seed": 42,
    "elapsed_ms": 10.0,
    "cancelled": False,
    "log": [],
    "checks": [
        {
            "name": "count@cycle11[spec]",
            "status": "FAIL",
            "signal": "count",
            "cycle": 11,
            "time_ns": 110,
            "expected": "00000001",
            "actual": "00000010",
            "source": "spec",
            "seed": 42,
            "elapsed_ms": 0.3,
            "message": "mismatch",
        }
    ],
    "errors": [],
})

SAMPLE_ERROR_SYNTAX = json.dumps({
    "schema_version": "1",
    "module": "",
    "status": "ERROR",
    "seed": None,
    "elapsed_ms": 0.5,
    "cancelled": False,
    "log": [],
    "checks": [],
    "errors": [
        {
            "file": "counter.sv",
            "line": 5,
            "column": 3,
            "severity": "error",
            "message": "expected ';', got '?'",
            "code": "E001",
        }
    ],
})

SAMPLE_SKIP = json.dumps({
    "schema_version": "1",
    "module": "counter",
    "status": "SKIP",
    "seed": None,
    "elapsed_ms": 0.0,
    "cancelled": False,
    "log": [],
    "checks": [],
    "errors": [],
})

SAMPLE_UNKNOWN_SCHEMA = json.dumps({
    "schema_version": "99",
    "status": "PASS",
    "checks": [],
    "errors": [],
})

SAMPLE_FUTURE_FIELDS = json.dumps({
    "schema_version": "1",
    "module": "counter",
    "status": "PASS",
    "seed": 42,
    "elapsed_ms": 5.0,
    "cancelled": False,
    "log": [],
    "checks": [],
    "errors": [],
    # 将来追加される予定のフィールド（現在は無視されるべき）
    "summary": {"test_cases": 3, "elapsed_ms": 100.0},
    "unknown_new_field": "value",
})


class TestParserPass:
    def test_status_is_pass(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.success is True
        assert result.status == "PASS"

    def test_checks_are_parsed(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert len(result.checks) == 1
        c = result.checks[0]
        assert c.name == "count@cycle11[spec]"
        assert c.signal == "count"
        assert c.cycle == 11
        assert c.time_ns == 110
        assert c.expected == "00000001"
        assert c.actual == "00000001"
        assert c.status == "PASS"

    def test_errors_empty(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.errors == []

    def test_user_message_contains_pass_indicator(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert "✅" in result.user_message

    def test_raw_output_preserved(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.raw_output == SAMPLE_PASS


class TestParserFail:
    def test_status_is_fail(self):
        result = _parse_deltasim_result(SAMPLE_FAIL)
        assert result.success is False
        assert result.status == "FAIL"

    def test_failed_check_details(self):
        result = _parse_deltasim_result(SAMPLE_FAIL)
        assert len(result.checks) == 1
        c = result.checks[0]
        assert c.status == "FAIL"
        assert c.expected == "00000001"
        assert c.actual == "00000010"

    def test_user_message_contains_fail_indicator(self):
        result = _parse_deltasim_result(SAMPLE_FAIL)
        assert "❌" in result.user_message

    def test_user_message_contains_signal_info(self):
        result = _parse_deltasim_result(SAMPLE_FAIL)
        assert "count" in result.user_message


class TestParserError:
    def test_status_is_error(self):
        result = _parse_deltasim_result(SAMPLE_ERROR_SYNTAX)
        assert result.success is False
        assert result.status == "ERROR"

    def test_error_details_parsed(self):
        result = _parse_deltasim_result(SAMPLE_ERROR_SYNTAX)
        assert len(result.errors) == 1
        e = result.errors[0]
        assert e.file == "counter.sv"
        assert e.line == 5
        assert e.column == 3
        assert e.severity == "error"
        assert e.code == "E001"

    def test_user_message_is_beginner_friendly(self):
        result = _parse_deltasim_result(SAMPLE_ERROR_SYNTAX)
        # セミコロンのエラーを初心者向けに言い換えていること
        assert "セミコロン" in result.user_message or "E001" in result.user_message or "counter.sv" in result.user_message

    def test_user_message_contains_error_indicator(self):
        result = _parse_deltasim_result(SAMPLE_ERROR_SYNTAX)
        assert "❌" in result.user_message


class TestParserSkip:
    def test_status_is_skip(self):
        result = _parse_deltasim_result(SAMPLE_SKIP)
        assert result.status == "SKIP"

    def test_skip_message(self):
        result = _parse_deltasim_result(SAMPLE_SKIP)
        assert "スキップ" in result.user_message


class TestParserSchemaVersion:
    def test_unsupported_schema_version(self):
        result = _parse_deltasim_result(SAMPLE_UNKNOWN_SCHEMA)
        assert result.success is False
        # バージョン不一致の初心者向けメッセージを返すこと
        assert "schema_version" in result.user_message or "バージョン" in result.user_message

    def test_supported_schema_version(self):
        assert SUPPORTED_SCHEMA_VERSION == "1"


class TestParserRobustness:
    def test_empty_input(self):
        result = _parse_deltasim_result("")
        assert result.success is False
        assert result.user_message  # 何らかのメッセージがあること

    def test_invalid_json(self):
        result = _parse_deltasim_result("not valid json {{{")
        assert result.success is False

    def test_future_unknown_fields_are_ignored(self):
        """将来追加されるフィールドが存在しても正常に動作する"""
        result = _parse_deltasim_result(SAMPLE_FUTURE_FIELDS)
        assert result.success is True
        assert result.status == "PASS"

    def test_null_check_message(self):
        """checks[].message が null でもエラーにならない"""
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.checks[0].message is None


class TestStubSimulator:
    def test_is_not_available(self):
        stub = StubSimulator()
        assert stub.is_available() is False

    def test_run_returns_result(self):
        stub = StubSimulator()
        result = stub.run([], None)
        assert isinstance(result, SimulationResult)
        assert result.success is False
        assert result.user_message

    def test_run_message_mentions_puzzle(self):
        stub = StubSimulator()
        result = stub.run([], None)
        assert "パズル" in result.user_message or "HDL" in result.user_message
