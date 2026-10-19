"""
deltasim CLI 統合テスト（実機確認）

第6・7章の answer.sv が deltasim test で実際に PASS することを確認する。
また wrong_codes/ の各ファイルが manifest.yaml で指定した期待値通りに動作することを確認する。

  expected: FAIL                → deltasim で FAIL/ERROR になることをアサート
  expected: PASS_KNOWN_LIMITATION → 現在 PASS することをアサート
       ↑ deltasim がサブサイクル刺激に対応した時点でこのアサートが壊れます。
         壊れたら manifest.yaml を FAIL に書き換え、FAILを確認するテストに更新してください。

deltasim がインストールされていない環境では自動的にスキップされる。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

DATA_ROOT = Path(__file__).parent.parent / "fpga_study" / "data"

DELTASIM_AVAILABLE = shutil.which("deltasim") is not None

skip_if_no_deltasim = pytest.mark.skipif(
    not DELTASIM_AVAILABLE,
    reason="deltasim がインストールされていません（pip install deltasim）",
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


@skip_if_no_deltasim
class TestChapter06Answers:
    """第6章の正解例がすべて PASS することを確認"""

    def test_lesson01_and_gate_passes(self):
        """ANDゲート (assign) の正解例が PASS"""
        answer = DATA_ROOT / "chapter06" / "lesson01" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["schema_version"] == "2"
        assert result["status"] == "PASS", (
            f"ANDゲートの正解例が PASS しません。status={result['status']}"
        )

    def test_lesson02_mux_passes(self):
        """2:1 MUX (always_comb) の正解例が PASS"""
        answer = DATA_ROOT / "chapter06" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson02" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS"

    def test_lesson03_dff_passes(self):
        """Dフリップフロップ (always_ff) の正解例が PASS"""
        answer = DATA_ROOT / "chapter06" / "lesson03" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS"
        assert "cases" in result

    def test_lesson03_dff_result_structure(self):
        """結果JSON が schema_version 2 の構造を持つことを確認"""
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
        """y=0固定の誤りコードが FAIL になることを確認"""
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            wrong_sv = Path(tmp) / "wrong.sv"
            wrong_sv.write_text(
                "module and_gate(input logic clk, input logic a, input logic b, output logic y);\n"
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


@skip_if_no_deltasim
class TestChapter07Answers:
    """第7章の正解例がすべて PASS することを確認"""

    def test_lesson02_counter_passes(self):
        """4ビットカウンタの正解例が PASS"""
        answer = DATA_ROOT / "chapter07" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()
        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS"

    def test_lesson02_counter_vcd_output(self):
        """カウンタのシミュレーションで VCD ファイルが出力されることを確認"""
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


@skip_if_no_deltasim
class TestWrongCodesManifest:
    """
    manifest.yaml で定義された wrong_codes をすべて検証する。

    FAIL                  → FAIL/ERROR になることをアサート
    PASS_KNOWN_LIMITATION → 現在 PASS することをアサート
                            ※ PASS でなくなったらdeltasimがサブサイクル対応した合図
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
            assert actual_status == "PASS", (
                f"[⚠️ 既知制約の変化を検出] {filename} が {actual_status} になりました。\n"
                f"deltasim がサブサイクル刺激に対応した可能性があります。\n"
                f"対応: manifest.yaml の expected を FAIL に変更し、README.md を更新してください。\n"
                f"ファイル: {wrong_sv}\n"
                f"理由: {reason}"
            )

        elif expected == "RULE_VIOLATION_UNDETECTABLE":
            # スタイル違反だが機能的に正しい。deltasim 改善後も PASS のまま。
            assert actual_status == "PASS", (
                f"[⚠️ RULE_VIOLATION_UNDETECTABLE が PASS でなくなりました] {filename}: {actual_status}\n"
                f"これはスタイル違反のため機能的には正しいはずです。\n"
                f"spec の変更や deltasim の挙動変化を確認してください（サブサイクル対応では壊れないはず）。\n"
                f"理由: {reason}"
            )

        elif expected == "FAIL_DUE_TO_DELTASIM_BUG":
            # deltasim バグにより現在 FAIL する。バグ修正後は PASS になる予定。
            assert actual_status in ("FAIL", "ERROR"), (
                f"[⚠️ FAIL_DUE_TO_DELTASIM_BUG が PASS になりました] {filename}: {actual_status}\n"
                f"deltasim のバグが修正された可能性があります。\n"
                f"対応: manifest.yaml のエントリを RULE_VIOLATION_UNDETECTABLE または\n"
                f"PASS_KNOWN_LIMITATION に変更し、仕様考案係に確認してください。\n"
                f"理由: {reason}"
            )

        else:
            pytest.fail(f"manifest.yaml の expected 値が不明: {expected!r}")


# ── deltasim バージョン確認 ────────────────────────────────────────────


@skip_if_no_deltasim
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
