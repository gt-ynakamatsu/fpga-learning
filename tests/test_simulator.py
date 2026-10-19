"""
deltasim CLI 連携パーサのテスト
docs/api.md §2.2 / §13.2 のサンプルJSONを使って検証する
schema_version "2" 準拠
"""

from __future__ import annotations

import json

import pytest

from fpga_study.simulator import (
    SUPPORTED_SCHEMA_MAJOR,
    CaseResult,
    CheckResult,
    SimulationResult,
    StubSimulator,
    _parse_deltasim_result,
)


# ── docs/api.md §2.2 / §13.2 のサンプルJSON ──────────────────────────

SAMPLE_PASS = json.dumps({
    "schema_version": "2",
    "module": "counter",
    "status": "PASS",
    "seed": 42,
    "elapsed_ms": 12.3,
    "summary": {"elapsed_ms": 12.3},
    "cancelled": False,
    "log": [],
    "cases": [
        {
            "name": "basic",
            "status": "PASS",
            "seed": 42,
            "elapsed_ms": 12.3,
            "message": None,
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
            "log": [],
        }
    ],
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

SAMPLE_FAIL_MULTI_CASE = json.dumps({
    "schema_version": "2",
    "module": "counter",
    "status": "FAIL",
    "seed": 42,
    "elapsed_ms": 50.3,
    "summary": {"elapsed_ms": 50.3},
    "cancelled": False,
    "log": [],
    "cases": [
        {
            "name": "basic",
            "status": "PASS",
            "seed": 42,
            "elapsed_ms": 12.3,
            "message": None,
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
            "log": [],
        },
        {
            "name": "overflow",
            "status": "FAIL",
            "seed": 100,
            "elapsed_ms": 15.1,
            "message": None,
            "checks": [
                {
                    "name": "count@cycle258[spec]",
                    "status": "FAIL",
                    "signal": "count",
                    "cycle": 258,
                    "time_ns": 2580,
                    "expected": "11111111",
                    "actual": "00000000",
                    "source": "spec",
                    "seed": 100,
                    "elapsed_ms": 0.8,
                    "message": "mismatch",
                }
            ],
            "log": [],
        },
        {
            "name": "skip_example",
            "status": "SKIP",
            "seed": None,
            "elapsed_ms": 0.1,
            "message": "CI対象外",
            "checks": [],
            "log": ["CI対象外"],
        },
    ],
    "checks": [],
    "errors": [],
})

SAMPLE_ERROR_SYNTAX = json.dumps({
    "schema_version": "2",
    "module": "",
    "status": "ERROR",
    "seed": None,
    "elapsed_ms": 0.5,
    "summary": {"elapsed_ms": 0.5},
    "cancelled": False,
    "log": [],
    "cases": [],
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

SAMPLE_E_NO_CASE = json.dumps({
    "schema_version": "2",
    "module": "counter",
    "status": "ERROR",
    "seed": None,
    "elapsed_ms": 0.1,
    "summary": {"elapsed_ms": 0.1},
    "cancelled": False,
    "log": [],
    "cases": [],
    "checks": [],
    "errors": [
        {
            "file": "",
            "line": 0,
            "column": 0,
            "severity": "error",
            "message": "Pattern 'nonexistent_*' matched no test cases",
            "code": "E_NO_CASE",
        }
    ],
})

SAMPLE_SKIP = json.dumps({
    "schema_version": "2",
    "module": "counter",
    "status": "SKIP",
    "seed": None,
    "elapsed_ms": 0.0,
    "summary": {"elapsed_ms": 0.0},
    "cancelled": False,
    "log": [],
    "cases": [],
    "checks": [],
    "errors": [],
})

SAMPLE_SCHEMA_V1_MAJOR_MISMATCH = json.dumps({
    "schema_version": "1",
    "status": "PASS",
    "cases": [],
    "checks": [],
    "errors": [],
})

SAMPLE_SCHEMA_V3_MAJOR_MISMATCH = json.dumps({
    "schema_version": "3",
    "status": "PASS",
    "cases": [],
    "checks": [],
    "errors": [],
})

SAMPLE_SCHEMA_V2_MINOR_COMPAT = json.dumps({
    "schema_version": "2.1",
    "module": "counter",
    "status": "PASS",
    "seed": 1,
    "elapsed_ms": 1.0,
    "summary": {"elapsed_ms": 1.0},
    "cancelled": False,
    "log": [],
    "cases": [],
    "checks": [],
    "errors": [],
})

SAMPLE_FUTURE_FIELDS = json.dumps({
    "schema_version": "2",
    "module": "counter",
    "status": "PASS",
    "seed": 42,
    "elapsed_ms": 5.0,
    "summary": {"elapsed_ms": 5.0},
    "cancelled": False,
    "log": [],
    "cases": [],
    "checks": [],
    "errors": [],
    "summary": {"elapsed_ms": 5.0, "test_cases": 3},
    "unknown_new_field": "value",
    "truncated_at": 50000,
})

SAMPLE_NO_CASES_FIELD = json.dumps({
    "schema_version": "2",
    "module": "counter",
    "status": "PASS",
    "seed": 42,
    "elapsed_ms": 5.0,
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


# ── PASS テスト ────────────────────────────────────────────────────────


class TestParserPass:
    def test_status_is_pass(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.success is True
        assert result.status == "PASS"

    def test_cases_are_parsed(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert len(result.cases) == 1
        case = result.cases[0]
        assert case.name == "basic"
        assert case.status == "PASS"
        assert case.seed == 42
        assert case.elapsed_ms == 12.3

    def test_case_checks_are_parsed(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        case = result.cases[0]
        assert len(case.checks) == 1
        c = case.checks[0]
        assert c.signal == "count"
        assert c.cycle == 11
        assert c.time_ns == 110
        assert c.expected == "00000001"
        assert c.actual == "00000001"
        assert c.status == "PASS"

    def test_top_level_checks_parsed(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert len(result.checks) == 1

    def test_summary_elapsed_ms(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.summary_elapsed_ms == 12.3

    def test_user_message_contains_pass_indicator(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert "✅" in result.user_message

    def test_raw_output_preserved(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.raw_output == SAMPLE_PASS

    def test_errors_empty(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.errors == []


# ── マルチケース FAIL テスト ──────────────────────────────────────────


class TestParserMultiCaseFail:
    def test_status_is_fail(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        assert result.success is False
        assert result.status == "FAIL"

    def test_cases_count(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        assert len(result.cases) == 3

    def test_pass_case(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        basic = next(c for c in result.cases if c.name == "basic")
        assert basic.status == "PASS"

    def test_fail_case(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        overflow = next(c for c in result.cases if c.name == "overflow")
        assert overflow.status == "FAIL"
        assert len(overflow.checks) == 1
        assert overflow.checks[0].expected == "11111111"
        assert overflow.checks[0].actual == "00000000"

    def test_skip_case(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        skip_c = next(c for c in result.cases if c.name == "skip_example")
        assert skip_c.status == "SKIP"
        assert skip_c.message == "CI対象外"

    def test_user_message_shows_failed_case(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        assert "❌" in result.user_message
        assert "overflow" in result.user_message

    def test_summary_elapsed_ms(self):
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        assert result.summary_elapsed_ms == 50.3


# ── ERROR（構文エラー）テスト ─────────────────────────────────────────


class TestParserSyntaxError:
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
        assert "❌" in result.user_message
        assert ("セミコロン" in result.user_message or "counter.sv" in result.user_message)

    def test_cases_empty(self):
        result = _parse_deltasim_result(SAMPLE_ERROR_SYNTAX)
        assert result.cases == []


# ── E_NO_CASE テスト ──────────────────────────────────────────────────


class TestParserENoCase:
    def test_status_is_error(self):
        result = _parse_deltasim_result(SAMPLE_E_NO_CASE)
        assert result.success is False
        assert result.status == "ERROR"

    def test_e_no_case_error_code(self):
        result = _parse_deltasim_result(SAMPLE_E_NO_CASE)
        assert len(result.errors) == 1
        assert result.errors[0].code == "E_NO_CASE"

    def test_user_message_is_beginner_friendly(self):
        result = _parse_deltasim_result(SAMPLE_E_NO_CASE)
        assert "ケース" in result.user_message or "pattern" in result.user_message.lower()
        assert "nonexistent_*" in result.user_message or "E_NO_CASE" in result.user_message

    def test_user_message_not_technical(self):
        result = _parse_deltasim_result(SAMPLE_E_NO_CASE)
        # 初心者向けメッセージなのでスタックトレースなどがないこと
        assert "Traceback" not in result.user_message


# ── SKIP テスト ────────────────────────────────────────────────────────


class TestParserSkip:
    def test_status_is_skip(self):
        result = _parse_deltasim_result(SAMPLE_SKIP)
        assert result.status == "SKIP"
        assert result.success is False

    def test_skip_message(self):
        result = _parse_deltasim_result(SAMPLE_SKIP)
        assert "スキップ" in result.user_message


# ── バージョン互換性テスト ─────────────────────────────────────────────


class TestParserSchemaVersion:
    def test_supported_major_version(self):
        assert SUPPORTED_SCHEMA_MAJOR == "2"

    def test_v2_is_supported(self):
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.success is True

    def test_v2_1_minor_is_compatible(self):
        """マイナーバージョン違いは互換として扱う"""
        result = _parse_deltasim_result(SAMPLE_SCHEMA_V2_MINOR_COMPAT)
        assert result.success is True

    def test_v1_major_mismatch_warns(self):
        """v1はメジャー不一致なので警告"""
        result = _parse_deltasim_result(SAMPLE_SCHEMA_V1_MAJOR_MISMATCH)
        assert result.success is False
        assert "schema_version" in result.user_message or "バージョン" in result.user_message

    def test_v3_major_mismatch_warns(self):
        """v3はメジャー不一致なので警告"""
        result = _parse_deltasim_result(SAMPLE_SCHEMA_V3_MAJOR_MISMATCH)
        assert result.success is False
        assert "schema_version" in result.user_message or "バージョン" in result.user_message

    def test_warning_message_mentions_update(self):
        result = _parse_deltasim_result(SAMPLE_SCHEMA_V1_MAJOR_MISMATCH)
        assert "更新" in result.user_message or "バージョン" in result.user_message


# ── 堅牢性テスト ──────────────────────────────────────────────────────


class TestParserRobustness:
    def test_empty_input(self):
        result = _parse_deltasim_result("")
        assert result.success is False
        assert result.user_message

    def test_invalid_json(self):
        result = _parse_deltasim_result("not valid json {{{")
        assert result.success is False

    def test_future_unknown_fields_are_ignored(self):
        """将来追加されるフィールドが存在しても正常に動作する"""
        result = _parse_deltasim_result(SAMPLE_FUTURE_FIELDS)
        assert result.success is True
        assert result.status == "PASS"

    def test_truncated_at_ignored(self):
        """truncated_at フィールドは無視する"""
        result = _parse_deltasim_result(SAMPLE_FUTURE_FIELDS)
        assert result.success is True

    def test_no_cases_field_falls_back_to_checks(self):
        """cases フィールドがない旧形式でもエラーにならない"""
        result = _parse_deltasim_result(SAMPLE_NO_CASES_FIELD)
        assert result.success is True
        assert result.cases == []
        assert len(result.checks) == 1

    def test_null_check_message(self):
        """checks[].message が null でもエラーにならない"""
        result = _parse_deltasim_result(SAMPLE_PASS)
        assert result.cases[0].checks[0].message is None

    def test_case_message_field(self):
        """cases[].message フィールドが正しくパースされる"""
        result = _parse_deltasim_result(SAMPLE_FAIL_MULTI_CASE)
        skip_c = next(c for c in result.cases if c.name == "skip_example")
        assert skip_c.message == "CI対象外"


# ── StubSimulator テスト ──────────────────────────────────────────────


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

    def test_run_status_is_skip(self):
        stub = StubSimulator()
        result = stub.run([], None)
        assert result.status == "SKIP"
