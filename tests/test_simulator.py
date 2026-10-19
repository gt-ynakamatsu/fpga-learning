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
        # ケース名（英語）は user_message に含めない（フロントエンドが表示する）
        assert "ケース" in result.user_message or "不合格" in result.user_message

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


class TestLoopAndInternalErrors:
    """E_DELTA_LIMIT / E_LOOP_LIMIT / E_INTERNAL のユニットテスト"""

    def _make_result(self, error_code: str) -> str:
        import json
        return json.dumps({
            "schema_version": "2",
            "deltasim_version": "0.2.1",
            "status": "ERROR",
            "cases": [],
            "checks": [],
            "errors": [{"file": "", "line": 0, "column": 0,
                        "severity": "error", "message": f"{error_code}: 詳細", "code": error_code}],
            "warnings": [],
        })

    def test_e_delta_limit_gives_loop_message(self):
        result = _parse_deltasim_result(self._make_result("E_DELTA_LIMIT"))
        assert "回路が終わらない" in result.user_message, result.user_message
        assert result.status == "ERROR"

    def test_e_loop_limit_gives_loop_message(self):
        result = _parse_deltasim_result(self._make_result("E_LOOP_LIMIT"))
        assert "回路が終わらない" in result.user_message, result.user_message

    def test_e_internal_gives_internal_message(self):
        result = _parse_deltasim_result(self._make_result("E_INTERNAL"))
        assert "採点ツールの不具合" in result.user_message, result.user_message

    def test_empty_json_gives_internal_message(self):
        """JSON が空のとき = E_INTERNAL 扱い（想定外の異常終了）"""
        result = _parse_deltasim_result("", "")
        assert "採点ツールの不具合" in result.user_message, result.user_message
        assert result.status == "ERROR"

    def test_case_level_e_delta_limit_gives_loop_message(self):
        """cases[].errors に E_DELTA_LIMIT がある場合も検出"""
        import json
        data = {
            "schema_version": "2",
            "deltasim_version": "0.2.1",
            "status": "ERROR",
            "cases": [{"name": "c1", "status": "ERROR", "seed": 0,
                       "elapsed_ms": 0.1, "checks": [], "log": [],
                       "errors": [{"file": "", "line": 0, "column": 0,
                                   "severity": "error", "message": "E_DELTA_LIMIT: ...",
                                   "code": "E_DELTA_LIMIT"}],
                       "warnings": []}],
            "checks": [],
            "errors": [],
            "warnings": [],
        }
        result = _parse_deltasim_result(json.dumps(data))
        assert "回路が終わらない" in result.user_message, result.user_message


class TestParserWarnings:
    """warnings フィールドのパース（§15.12 W_UNKNOWN_KEY など）"""

    def test_warnings_absent_treated_as_empty(self):
        """warnings フィールドが absent (None) の場合は空リストとして扱う"""
        data = {
            "schema_version": "2", "status": "PASS",
            "cases": [], "checks": [], "errors": [],
            # warnings フィールドなし
        }
        import json
        result = _parse_deltasim_result(json.dumps(data))
        assert result.warnings == []

    def test_warnings_null_treated_as_empty(self):
        """warnings が null の場合も空リストとして扱う"""
        import json
        data = {
            "schema_version": "2", "status": "PASS",
            "cases": [], "checks": [], "errors": [],
            "warnings": None,
        }
        result = _parse_deltasim_result(json.dumps(data))
        assert result.warnings == []

    def test_warnings_empty_list(self):
        """warnings が空リストの場合"""
        import json
        data = {
            "schema_version": "2", "status": "PASS",
            "cases": [], "checks": [], "errors": [],
            "warnings": [],
        }
        result = _parse_deltasim_result(json.dumps(data))
        assert result.warnings == []

    def test_w_unknown_key_in_warnings(self):
        """W_UNKNOWN_KEY ワーニングがパースされユーザーメッセージに含まれる"""
        import json
        data = {
            "schema_version": "2", "status": "PASS",
            "cases": [], "checks": [], "errors": [],
            "warnings": [
                {"code": "W_UNKNOWN_KEY", "message": "stimulus[0]: 不明なキー 'foo' は無視されます"}
            ],
        }
        result = _parse_deltasim_result(json.dumps(data))
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "W_UNKNOWN_KEY"
        assert "foo" in result.warnings[0].message
        # ユーザーメッセージにワーニングが含まれる
        assert "不明なキー" in result.user_message or "W_UNKNOWN_KEY" in result.user_message

    def test_unknown_warning_code_displayed(self):
        """未知のワーニングコードも表示される（非致命的）"""
        import json
        data = {
            "schema_version": "2", "status": "PASS",
            "cases": [], "checks": [], "errors": [],
            "warnings": [
                {"code": "W_FUTURE_CODE", "message": "将来追加されるワーニング"}
            ],
        }
        result = _parse_deltasim_result(json.dumps(data))
        assert result.success is True  # PASS のまま
        assert len(result.warnings) == 1


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


class TestE001JapaneseHints:
    """§11.20 E001 エラーの2行目日本語ヒント"""

    def _make_error(self, message, line=1):
        from fpga_study.simulator import ErrorDetail
        return ErrorDetail(file="d.sv", line=line, column=0,
                           severity="error", message=message, code="E001")

    def test_comma_missing_hint(self):
        """expected ')' got 'output' → カンマが抜けています"""
        from fpga_study.simulator import _format_e001
        e = self._make_error("expected ')', got 'output'")
        result = _format_e001(e)
        assert "カンマ" in result or "," in result, f"カンマヒントが出ません: {result!r}"
        assert "書き方にまちがいがあります" in result

    def test_bracket_missing_hint(self):
        """expected ')' got ';' → ) が足りません"""
        from fpga_study.simulator import _format_e001
        e = self._make_error("expected ')', got ';'", line=2)
        result = _format_e001(e)
        assert ")" in result or "括弧" in result, f"括弧ヒントが出ません: {result!r}"

    def test_end_missing_hint(self):
        """got KW ('endmodule') → end が足りません"""
        from fpga_study.simulator import _format_e001
        e = self._make_error("expected token type ID, got KW ('endmodule')", line=4)
        result = _format_e001(e)
        assert "end" in result.lower(), f"endヒントが出ません: {result!r}"

    def test_no_module_hint(self):
        """No module declaration found → module がありません"""
        from fpga_study.simulator import _format_e001
        e = self._make_error("No module declaration found", line=0)
        result = _format_e001(e)
        assert "module" in result, f"moduleヒントが出ません: {result!r}"

    def test_no_english_inline(self):
        """英語原文は見出し直下・→ に出ない（§11.22）"""
        from fpga_study.simulator import _format_e001
        e = self._make_error("some untranslated english error message", line=3)
        result = _format_e001(e)
        # 英語原文がインラインに出ないこと
        assert "untranslated english error message" not in result, (
            f"英語原文がインライン表示されています: {result!r}"
        )
        assert "書き方にまちがいがあります" in result
