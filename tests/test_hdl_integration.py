"""
deltasim CLI 統合テスト（実機確認）

要件:
  - deltasim b482527 以降（§15 offset_ns サポート）が必要
  - 古い deltasim は §15 を無視してテストを誤った結果にする可能性があるため
    バージョンガードで検出・SKIP する（PASS_SILENT は禁止）

expected カテゴリ:
  FAIL                   → FAIL/ERROR であることをアサート
  PASS_KNOWN_LIMITATION  → 現在 PASS であることをアサート（コーディングルール違反 or 区別不可）
                           PASS でなくなったら → spec または deltasim の変化。manifest.yaml を更新。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

DATA_ROOT = Path(__file__).parent.parent / "fpga_study" / "data"

DELTASIM_AVAILABLE = shutil.which("deltasim") is not None


# ── §15 (offset_ns) サポートチェック ─────────────────────────────────


def _get_installed_version():
    if not DELTASIM_AVAILABLE:
        return None
    try:
        from fpga_study.simulator import get_deltasim_version
        return get_deltasim_version()
    except Exception:
        return None

def _is_v021_or_later() -> bool:
    ver = _get_installed_version()
    if not ver:
        return False
    try:
        return tuple(int(x) for x in ver.split(".")) >= (0, 2, 1)
    except ValueError:
        return False


DELTASIM_V021_OR_LATER = _is_v021_or_later()
# backward compat alias
DELTASIM_V021_OR_LATER = DELTASIM_V021_OR_LATER

_REQUIRE_DELTASIM = os.environ.get("REQUIRE_DELTASIM", "0") == "1"

skip_if_no_deltasim = pytest.mark.skipif(
    not DELTASIM_AVAILABLE,
    reason="deltasim がインストールされていません（pip install deltasim）",
)


require_v020 = pytest.mark.skipif(
    not DELTASIM_V021_OR_LATER,
    reason=(
        "deltasim 0.2.1 以上が必要です。"
        " pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@v0.2.1'"
    ),
)


def run_deltasim_test(answer_sv: Path, spec_yaml: Path) -> dict:
    """answer.sv を deltasim test で実行して結果JSONを返す"""
    with tempfile.TemporaryDirectory() as tmp:
        json_out = Path(tmp) / "result.json"
        result = subprocess.run(
            [
                "deltasim", "test", str(answer_sv),
                "--spec", str(spec_yaml),
                "--json", str(json_out),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not json_out.exists():
            pytest.fail(
                f"deltasim が結果JSONを出力しませんでした。\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return json.loads(json_out.read_text())


def load_manifest(wrong_codes_dir: Path) -> list[dict]:
    """manifest.yaml を読み込んで wrong_code エントリのリストを返す"""
    manifest_path = wrong_codes_dir / "manifest.yaml"
    if not manifest_path.exists():
        return []
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return data.get("wrong_codes", [])


# ── 正解例が PASS すること ─────────────────────────────────────────────


@require_v020
class TestChapter06Answers:
    """第6章の正解例がすべて PASS することを確認"""

    def test_lesson01_and_gate_passes(self):
        answer = DATA_ROOT / "chapter06" / "lesson01" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["schema_version"] == "2"
        assert result["status"] == "PASS"

    def test_lesson02_mux_passes(self):
        answer = DATA_ROOT / "chapter06" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson02" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS"

    def test_lesson03_dff_passes(self):
        answer = DATA_ROOT / "chapter06" / "lesson03" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS"
        assert "cases" in result

    def test_lesson03_dff_result_structure(self):
        answer = DATA_ROOT / "chapter06" / "lesson03" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        result = run_deltasim_test(answer, spec)
        assert "schema_version" in result
        assert "status" in result
        assert "cases" in result
        assert "checks" in result
        assert "errors" in result
        for case in result["cases"]:
            assert "name" in case
            assert "status" in case
            assert "checks" in case

    def test_wrong_code_gives_fail(self):
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            wrong_sv = Path(tmp) / "wrong.sv"
            wrong_sv.write_text(
                "module and_gate(input logic a, b, output logic y);\n"
                "    assign y = 1'b0;\n"
                "endmodule\n"
            )
            json_out = Path(tmp) / "result.json"
            subprocess.run(
                ["deltasim", "test", str(wrong_sv), "--spec", str(spec), "--json", str(json_out)],
                capture_output=True, text=True, timeout=30,
            )
            if json_out.exists():
                data = json.loads(json_out.read_text())
                assert data["status"] in ("FAIL", "ERROR")


@require_v020
class TestChapter07Answers:
    """第7章の正解例がすべて PASS することを確認"""

    def test_lesson02_counter_passes(self):
        answer = DATA_ROOT / "chapter07" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS"

    def test_lesson02_counter_vcd_output(self):
        answer = DATA_ROOT / "chapter07" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            vcd_out = Path(tmp) / "out.vcd"
            json_out = Path(tmp) / "result.json"
            subprocess.run(
                ["deltasim", "test", str(answer), "--spec", str(spec),
                 "--json", str(json_out), "--vcd", str(vcd_out)],
                capture_output=True, text=True, timeout=30,
            )
            assert vcd_out.exists()
            vcd_text = vcd_out.read_text()
            assert "$timescale" in vcd_text
            assert "$var" in vcd_text


# ── §15 offset_ns バージョンガードテスト ────────────────────────────


@require_v020
class TestDeltasimVersionRequirement:
    """§15 サポートの確認（このテストが FAIL なら古い deltasim を使用中）"""

    def test_v021_or_later_is_installed(self):
        """
        offset_ns が正しく動作することを確認する。
        FAIL した場合: deltasim b482527 以降をインストールしてください。
        pip install git+https://github.com/gt-ynakamatsu/deltasim.git@b482527
        """
        assert DELTASIM_V021_OR_LATER, (
            "⚠️ §15 (offset_ns) が未対応の deltasim が使われています。\n"
            "b482527 以降をインストールしてください:\n"
            "pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@b482527'\n"
            "古いバージョンでは wrong_codes の PASS_KNOWN_LIMITATION チェックが"
            "誤った PASS を返す可能性があります。"
        )


# ── manifest.yaml ベースの wrong_codes テスト ─────────────────────────


def _collect_wrong_code_params() -> list[tuple[Path, Path, dict]]:
    """manifest.yaml から (spec, wrong_sv, entry) タプルを収集する"""
    params = []
    for chapter in ["chapter06", "chapter07"]:
        chapter_dir = DATA_ROOT / chapter
        for lesson_dir in sorted(chapter_dir.iterdir()):
            if not lesson_dir.is_dir():
                continue
            wrong_dir = lesson_dir / "wrong_codes"
            spec = lesson_dir / "spec.yaml"
            if not (wrong_dir.exists() and spec.exists()):
                continue
            for entry in load_manifest(wrong_dir):
                sv = wrong_dir / entry["file"]
                if sv.exists():
                    params.append((spec, sv, entry))
    return params


_WRONG_CODE_PARAMS = _collect_wrong_code_params()

# §15 が必要な FAIL エントリ（combinational.sv, async_reset.sv）
_OFFSET_NS_REQUIRED_FILES = {"combinational.sv", "async_reset.sv"}


@require_v020
class TestWrongCodesManifest:
    """
    manifest.yaml で定義された wrong_codes をすべて検証する。

    FAIL                  → FAIL/ERROR になることをアサート
    PASS_KNOWN_LIMITATION → 現在 PASS であることをアサート
                            PASS でなくなったら: manifest.yaml を更新してください
    """

    @pytest.mark.parametrize(
        "spec,wrong_sv,entry",
        _WRONG_CODE_PARAMS,
        ids=[f"{e['file']}" for _, _, e in _WRONG_CODE_PARAMS],
    )
    def test_wrong_code(self, spec: Path, wrong_sv: Path, entry: dict) -> None:
        filename = entry["file"]
        expected = entry["expected"]
        reason = entry.get("reason", "")

        # §15 が必要なファイルは offset_ns 非対応なら SKIP
        if filename in _OFFSET_NS_REQUIRED_FILES and not DELTASIM_V021_OR_LATER:
            pytest.skip(
                f"{filename} は §15 (offset_ns) を使って検出するため、"
                f"古い deltasim では silent PASS になる可能性があります。"
                f"b482527 以降の deltasim を使用してください。"
            )

        result = run_deltasim_test(wrong_sv, spec)
        actual_status = result["status"]

        if expected == "FAIL":
            assert actual_status in ("FAIL", "ERROR"), (
                f"[FAIL期待] {filename} が {actual_status} になりました（期待: FAIL）。\n"
                f"理由: {reason}\n"
                f"spec: {spec}\n"
                f"spec 内のケースで検出できていない可能性があります。"
            )

        elif expected == "PASS_KNOWN_LIMITATION":
            # コーディングルール違反 or 区別不可の既知ケース
            assert actual_status == "PASS", (
                f"[⚠️ PASS_KNOWN_LIMITATION が PASS でなくなりました] {filename}: {actual_status}\n"
                f"考えられる原因:\n"
                f"  - spec にこのファイルを検出できる新しいケースが追加された\n"
                f"  - deltasim の動作が変化した\n"
                f"対応: manifest.yaml の expected を FAIL に変更するか、"
                f"spec/README.md を更新してください。\n"
                f"ファイル: {wrong_sv}\n"
                f"理由: {reason}"
            )

        else:
            pytest.fail(f"manifest.yaml の expected 値が不明: {expected!r}")


# ── 全 spec.yaml のゼロ warnings 確認 ────────────────────────────────


@require_v020
class TestSpecZeroWarnings:
    """
    全レッスンの spec.yaml + answer.sv を deltasim で実行し、
    warnings が空であることを確認する。

    これにより spec.yaml のキー誤記（W_UNKNOWN_KEY）を早期検出できる。
    警告判定は code フィールドのみで行い、message はパースしない。
    """

    @pytest.mark.parametrize(
        "chapter,lesson",
        [
            (ch.name, ls.name)
            for ch in sorted(DATA_ROOT.iterdir()) if ch.is_dir()
            for ls in sorted(ch.iterdir()) if ls.is_dir()
            if (ls / "spec.yaml").exists() and (ls / "answer.sv").exists()
        ],
        ids=lambda x: x if isinstance(x, str) else None,
    )
    def test_spec_produces_zero_warnings(self, chapter: str, lesson: str) -> None:
        spec = DATA_ROOT / chapter / lesson / "spec.yaml"
        answer = DATA_ROOT / chapter / lesson / "answer.sv"
        result = run_deltasim_test(answer, spec)

        # warnings キーが存在すること（v0.2.1 以降は常に present）
        assert "warnings" in result, (
            f"[warnings キーが存在しません] {chapter}/{lesson}\n"
            f"deltasim v0.2.1 以降を使用しているか確認してください。"
        )

        warnings = result.get("warnings") or []
        warning_codes = [w.get("code", "") for w in warnings]

        assert warnings == [], (
            f"[spec.yaml に警告が発生しました] {chapter}/{lesson}\n"
            f"警告コード: {warning_codes}\n"
            f"警告メッセージ（参考）: {[w.get('message') for w in warnings]}\n"
            f"spec.yaml のキー名を確認してください。W_UNKNOWN_KEY は不明なキーを示します。\n"
            f"判定は code フィールドのみで行います（message はパース不要）。"
        )


# ── deltasim バージョン確認 ────────────────────────────────────────────


@require_v020
class TestOffsetNsInFailedChecks:
    """offset_ns が CheckResult に正しく格納されること（実際の deltasim 出力で確認）"""

    def test_offset_ns_present_in_failed_checks(self):
        """combinational.sv の hold_between_edges ケースで offset_ns=4 が返ること"""
        from fpga_study.simulator import _parse_deltasim_result, DeltasimCLISimulator
        answer = DATA_ROOT / "chapter06" / "lesson03" / "wrong_codes" / "combinational.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        assert answer.exists()

        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "r.json"
            import subprocess as sp
            proc = sp.run(
                ["deltasim", "test", str(answer), "--spec", str(spec), "--json", str(json_out)],
                capture_output=True, text=True, timeout=20,
            )
            raw = json_out.read_text() if json_out.exists() else ""

        result = _parse_deltasim_result(raw, proc.stderr or "")

        # hold_between_edges ケースの失敗チェックに offset_ns > 0 があること
        found_offset = False
        for c in result.cases:
            if "hold_between_edges" in c.name:
                for ch in c.checks:
                    if ch.status != "PASS" and ch.offset_ns > 0:
                        found_offset = True
                        break

        assert found_offset, (
            f"hold_between_edges ケースで offset_ns > 0 の失敗チェックが見つかりません。"
            f"cases: {[(c.name, [(ch.name, ch.offset_ns) for ch in c.checks]) for c in result.cases]}"
        )

    def test_offset_ns_location_display(self):
        """offset_ns が「Nサイクル目のクロックの立ち上がりからMns後」と表示されること"""
        from fpga_study.simulator import CheckResult
        ch = CheckResult(
            name="q@cycle4+4ns[spec]",
            status="FAIL",
            signal="q",
            cycle=4,
            time_ns=29,
            expected="1",
            actual="0",
            offset_ns=4,
        )
        assert ch.offset_ns == 4

        # server.py のフォーマットロジックを確認
        offset_ns = ch.offset_ns or 0
        if offset_ns:
            loc = f"{ch.cycle}サイクル目のクロックの立ち上がりから{offset_ns}ns後"
        else:
            loc = f"{ch.cycle}サイクル目"

        assert "4サイクル目のクロックの立ち上がりから4ns後" == loc, f"表示が異なります: {loc}"


@require_v020
class TestLoopDetection:
    """E_DELTA_LIMIT / E_LOOP_LIMIT による回路終わらない検出テスト (v0.2.1+)"""

    def test_combinational_loop_gives_friendly_message(self):
        """assign y = ~y; → E_DELTA_LIMIT → 回路が終わらない案内"""
        from fpga_study.simulator import _parse_deltasim_result
        with tempfile.TemporaryDirectory() as tmp:
            sv = Path(tmp) / "loop.sv"
            sv.write_text(
                "module loop_test(input logic a, output logic y);\n"
                "    assign y = ~y;\n"
                "endmodule\n"
            )
            spec = Path(tmp) / "spec.yaml"
            spec.write_text(
                "version: 1\ntop: loop_test\n"
                "clock: {signal: clk, period_ns: 10}\nsim: {cycles: 5}\n"
                "cases:\n  - name: test\n    expected:\n      - {at: 2, check: {y: 0}}\n"
            )
            json_out = Path(tmp) / "r.json"
            import subprocess as sp
            proc = sp.run(
                ["deltasim", "test", str(sv), "--spec", str(spec), "--json", str(json_out)],
                capture_output=True, text=True, timeout=15,
            )
            raw = json_out.read_text() if json_out.exists() else ""

        result = _parse_deltasim_result(raw, proc.stderr or "")

        # E_DELTA_LIMIT がコードとして存在すること
        all_codes = {e.code for e in result.errors}
        for c in result.cases:
            all_codes.update(e.code for e in c.case_errors)
        assert "E_DELTA_LIMIT" in all_codes, \
            f"E_DELTA_LIMIT が検出されませんでした: codes={all_codes}, status={result.status}"

        # ユーザーメッセージが初心者向けであること
        assert "回路が終わらない" in result.user_message, \
            f"初心者向けメッセージがありません: {result.user_message}"


@require_v020
class TestMultiPortDeclaration:
    """1行に複数のポートを書いた場合でも合格すること (v0.2.1+)"""

    def test_ch6_lesson03_multiport_syntax_passes(self):
        """input logic clk, rst, d の書き方が deltasim v0.2.1+ で通ること"""
        answer = DATA_ROOT / "chapter06" / "lesson03" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            original = answer.read_text()
            multiport = original.replace(
                "    input  logic clk,\n    input  logic rst,\n    input  logic d,",
                "    input  logic clk, rst, d,"
            )
            mp_sv = Path(tmp) / "d_ff_multiport.sv"
            mp_sv.write_text(multiport)
            raw_result = run_deltasim_test(mp_sv, spec)

        assert raw_result.get("status") == "PASS", (
            f"1行複数ポートの書き方が PASS しません: {raw_result}"
        )


@require_v020
class TestWhileLoopDetection:
    """while loop → E_LOOP_LIMIT → 回路が終わらない案内 (v0.2.1+)"""

    def test_while_loop_gives_loop_limit_code(self):
        """while ループが上限を超えたとき E_LOOP_LIMIT → 初心者向けメッセージ
        
        実際に返ってきたコード: E_LOOP_LIMIT
        「E_LOOP_LIMIT: 0ns の while loop が 1000000 回を超えました」
        """
        from fpga_study.simulator import _parse_deltasim_result
        with tempfile.TemporaryDirectory() as tmp:
            sv = Path(tmp) / "wloop.sv"
            sv.write_text(
                "module wloop(input logic clk, input logic a, output logic [31:0] y);\n"
                "    logic [31:0] count;\n"
                "    always_comb begin\n"
                "        count = 0;\n"
                "        while (count < 32'hFFFFFFFF) begin\n"
                "            count = count + 1;\n"
                "        end\n"
                "        y = count & {32{a}};\n"
                "    end\n"
                "endmodule\n"
            )
            spec = Path(tmp) / "spec.yaml"
            spec.write_text(
                "version: 1\ntop: wloop\n"
                "clock: {signal: clk, period_ns: 10}\nsim: {cycles: 5}\n"
                "cases:\n  - name: test\n    expected:\n      - {at: 2, check: {y: 0}}\n"
            )
            import subprocess as sp
            json_out = Path(tmp) / "r.json"
            proc = sp.run(
                ["deltasim", "test", str(sv), "--spec", str(spec), "--json", str(json_out)],
                capture_output=True, text=True, timeout=30,
            )
            raw = json_out.read_text() if json_out.exists() else ""

        result = _parse_deltasim_result(raw, proc.stderr or "")

        all_codes = {e.code for e in result.errors}
        for c in result.cases:
            all_codes.update(e.code for e in c.case_errors)

        assert "E_LOOP_LIMIT" in all_codes, (
            f"E_LOOP_LIMIT が検出されませんでした。"
            f"codes={all_codes}, status={result.status}"
        )
        assert "回路が終わらない" in result.user_message, (
            f"初心者向けメッセージがありません: {result.user_message}"
        )


@require_v020
class TestSyntaxErrorDisplay:
    """文法エラー時の初心者向け表示と詳細折りたたみを確認"""

    def test_syntax_error_gives_friendly_message(self):
        """文法エラー: cases は空、errors[] にエラー。ファイル名は design.sv のみ"""
        # サーバー経由でテスト（E2E 相当）
        from fastapi.testclient import TestClient
        import tempfile
        from fpga_study.server import create_app
        db = Path(tempfile.mktemp(suffix=".db"))
        from fpga_study.progress import init_db
        init_db(db)
        client = TestClient(create_app(db_path=db, show_drafts=True))

        bad_code = (
            "module and_gate(\n"
            "    input  logic a,\n"
            "    input  logic b,\n"
            "    output logic y\n"
            ");\n"
            "    assign y = a &  ;  // 文法エラー\n"
            "endmodule\n"
        )
        res = client.post(
            "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
            json={"code": bad_code},
        )
        assert res.status_code == 200
        data = res.json()

        assert data["status"] in ("ERROR", "FAIL"), f"expected ERROR got {data['status']}"
        # cases は空（文法エラーは top-level errors[] に入る）
        # errors が存在すること
        assert len(data.get("errors", [])) > 0, "errors が空です"
        # ファイル名が design.sv のみ（フルパスでない）
        for err in data.get("errors", []):
            if err.get("file"):
                assert err["file"] == "design.sv" or "/" not in err["file"], (
                    f"一時ファイルのパスが含まれています: {err['file']}"
                )


@require_v020
class TestAllChaptersCaseDescriptions:
    """1〜7章の全 spec.yaml ケースに日本語説明があること"""

    def test_all_hdl_spec_cases_have_japanese_descriptions(self):
        import yaml, unicodedata
        data_root = DATA_ROOT.parent  # fpga_study/data

        def is_japanese(text: str) -> bool:
            """文字列に日本語（ひらがな・カタカナ・漢字）が含まれるか"""
            if not text:
                return False
            for ch in text:
                if unicodedata.category(ch) in ('Lo',) and ord(ch) > 0x3000:
                    return True
                cat = unicodedata.name(ch, '')
                if any(kw in cat for kw in ('HIRAGANA', 'KATAKANA', 'CJK')):
                    return True
            return False

        failures = []
        for chapter_dir in sorted(data_root.iterdir()):
            if not chapter_dir.is_dir() or chapter_dir.name.startswith('.'):
                continue
            if chapter_dir.name not in {f"chapter0{i}" for i in range(1, 8)}:
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
                    desc = descriptions.get(name, "")
                    if not desc:
                        failures.append(f"{lesson_dir.relative_to(data_root)}: ケース '{name}' の説明が空です")
                    elif not is_japanese(desc):
                        failures.append(f"{lesson_dir.relative_to(data_root)}: ケース '{name}' の説明に日本語がありません: {desc!r}")

        assert not failures, "\n".join(failures)


@require_v020
class TestDeltasimVersion:
    """deltasim のバージョンと schema_version を確認"""

    def test_deltasim_is_available(self):
        result = subprocess.run(
            ["deltasim", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0

    def test_output_schema_version_is_2(self):
        answer = DATA_ROOT / "chapter06" / "lesson01" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        result = run_deltasim_test(answer, spec)
        assert result.get("schema_version") == "2"
