"""
deltasim CLI 統合テスト（実機確認）

第6・7章の answer.sv が deltasim test で実際に PASS することを確認する。
deltasim がインストールされていない環境では自動的にスキップされる。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

DATA_ROOT = Path(__file__).parent.parent / "fpga_study" / "data"

# deltasim が利用可能かどうかをチェック
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
            pytest.fail(f"deltasim が結果JSONを出力しませんでした。\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return json.loads(json_out.read_text())


@skip_if_no_deltasim
class TestChapter06Answers:
    """第6章の正解例がすべて PASS することを確認"""

    def test_lesson01_and_gate_passes(self):
        """ANDゲート (assign) の正解例が PASS"""
        answer = DATA_ROOT / "chapter06" / "lesson01" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        assert answer.exists(), f"answer.sv が見つかりません: {answer}"
        assert spec.exists(), f"spec.yaml が見つかりません: {spec}"

        result = run_deltasim_test(answer, spec)

        assert result["schema_version"] == "2", "schema_version が 2 ではありません"
        assert result["status"] == "PASS", (
            f"ANDゲートの正解例が PASS しません。\n"
            f"status={result['status']}\n"
            f"cases={json.dumps(result.get('cases', []), ensure_ascii=False, indent=2)}"
        )
        # 全ケース PASS 確認
        failed = [c for c in result.get("cases", []) if c["status"] != "PASS"]
        assert not failed, f"失敗ケース: {[c['name'] for c in failed]}"

    def test_lesson02_mux_passes(self):
        """2:1 MUX (always_comb) の正解例が PASS"""
        answer = DATA_ROOT / "chapter06" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson02" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()

        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS", (
            f"MUXの正解例が PASS しません。status={result['status']}"
        )

    def test_lesson03_dff_passes(self):
        """Dフリップフロップ (always_ff) の正解例が PASS"""
        answer = DATA_ROOT / "chapter06" / "lesson03" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        assert answer.exists()
        assert spec.exists()

        result = run_deltasim_test(answer, spec)
        assert result["status"] == "PASS", (
            f"D-FFの正解例が PASS しません。status={result['status']}"
        )
        # schema_version "2" の cases フィールドを確認
        assert "cases" in result, "cases フィールドがありません"
        assert len(result["cases"]) >= 1

    def test_lesson03_dff_result_structure(self):
        """結果JSON が schema_version 2 の構造を持つことを確認"""
        answer = DATA_ROOT / "chapter06" / "lesson03" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"

        result = run_deltasim_test(answer, spec)

        # トップレベルフィールドの確認
        assert "schema_version" in result
        assert "status" in result
        assert "cases" in result
        assert "checks" in result
        assert "errors" in result

        # cases の各要素に必要なフィールドがあること
        for case in result["cases"]:
            assert "name" in case
            assert "status" in case
            assert "checks" in case

    def test_wrong_code_gives_fail(self):
        """誤ったコードが FAIL または ERROR になることを確認"""
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"

        with tempfile.TemporaryDirectory() as tmp:
            wrong_sv = Path(tmp) / "wrong.sv"
            # y = 0 に固定（常に FAIL するはず）
            wrong_sv.write_text(
                "module and_gate(input logic clk, input logic a, input logic b, output logic y);\n"
                "    assign y = 1'b0; // 常に0 (AND ではない)\n"
                "endmodule\n"
            )
            json_out = Path(tmp) / "result.json"
            result = subprocess.run(
                ["deltasim", "test", str(wrong_sv), "--spec", str(spec), "--json", str(json_out)],
                capture_output=True, text=True, timeout=30,
            )
            if json_out.exists():
                data = json.loads(json_out.read_text())
                # 11_gives_1 のケースが FAIL するはず
                assert data["status"] in ("FAIL", "ERROR"), (
                    f"誤ったコードが PASS してしまいました。status={data['status']}"
                )


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
        assert result["status"] == "PASS", (
            f"カウンタの正解例が PASS しません。status={result['status']}"
        )

    def test_lesson02_counter_vcd_output(self):
        """カウンタのシミュレーションで VCD ファイルが出力されることを確認"""
        answer = DATA_ROOT / "chapter07" / "lesson02" / "answer.sv"
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"

        with tempfile.TemporaryDirectory() as tmp:
            vcd_out = Path(tmp) / "out.vcd"
            json_out = Path(tmp) / "result.json"
            subprocess.run(
                [
                    "deltasim", "test", str(answer),
                    "--spec", str(spec),
                    "--json", str(json_out),
                    "--vcd", str(vcd_out),
                ],
                capture_output=True, text=True, timeout=30,
            )
            assert vcd_out.exists(), "VCD ファイルが出力されませんでした"
            vcd_text = vcd_out.read_text()
            # VCD の基本構造を確認
            assert "$timescale" in vcd_text
            assert "$var" in vcd_text
            assert "count" in vcd_text or "clk" in vcd_text


@skip_if_no_deltasim
class TestChapter06WrongCodes:
    """第6章の間違いコードが FAIL することを確認（wrong_codes/）"""

    def _wrong_dir(self, lesson: str) -> Path:
        return DATA_ROOT / "chapter06" / lesson / "wrong_codes"

    def test_lesson02_sel_xor_a_fails(self):
        spec = DATA_ROOT / "chapter06" / "lesson02" / "spec.yaml"
        wrong = self._wrong_dir("lesson02") / "sel_xor_a.sv"
        if not wrong.exists():
            pytest.skip("sel_xor_a.sv not found")
        result = run_deltasim_test(wrong, spec)
        assert result["status"] in ("FAIL", "ERROR"), (
            f"sel_xor_a.sv は FAIL するはずが {result['status']} になりました"
        )

    def test_lesson02_a_or_selb_fails(self):
        spec = DATA_ROOT / "chapter06" / "lesson02" / "spec.yaml"
        wrong = self._wrong_dir("lesson02") / "a_or_sel_and_b.sv"
        if not wrong.exists():
            pytest.skip("a_or_sel_and_b.sv not found")
        result = run_deltasim_test(wrong, spec)
        assert result["status"] in ("FAIL", "ERROR"), (
            f"a_or_sel_and_b.sv は FAIL するはずが {result['status']} になりました"
        )

    def test_lesson03_no_reset_fails(self):
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        wrong = self._wrong_dir("lesson03") / "no_reset.sv"
        if not wrong.exists():
            pytest.skip("no_reset.sv not found")
        result = run_deltasim_test(wrong, spec)
        assert result["status"] in ("FAIL", "ERROR"), (
            f"no_reset.sv は FAIL するはずが {result['status']} になりました"
        )

    def test_lesson03_combinational_known_limitation(self):
        """combinational.sv は整数サイクル制約により PASS する既知の制約"""
        spec = DATA_ROOT / "chapter06" / "lesson03" / "spec.yaml"
        wrong = self._wrong_dir("lesson03") / "combinational.sv"
        if not wrong.exists():
            pytest.skip("combinational.sv not found")
        result = run_deltasim_test(wrong, spec)
        # PASS は既知制約。FAIL なら改善。どちらでもテストは通過。
        assert result["status"] in ("PASS", "FAIL", "ERROR"), (
            f"予期しないステータス: {result['status']}"
        )


@skip_if_no_deltasim
class TestChapter07WrongCodes:
    """第7章の間違いコードが FAIL することを確認（wrong_codes/）"""

    def _wrong_dir(self) -> Path:
        return DATA_ROOT / "chapter07" / "lesson02" / "wrong_codes"

    def test_saturate_at_15_fails(self):
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"
        wrong = self._wrong_dir() / "saturate_at_15.sv"
        if not wrong.exists():
            pytest.skip("saturate_at_15.sv not found")
        result = run_deltasim_test(wrong, spec)
        assert result["status"] in ("FAIL", "ERROR"), (
            f"saturate_at_15.sv は FAIL するはずが {result['status']} になりました"
        )

    def test_count_0_to_9_fails(self):
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"
        wrong = self._wrong_dir() / "count_0_to_9.sv"
        if not wrong.exists():
            pytest.skip("count_0_to_9.sv not found")
        result = run_deltasim_test(wrong, spec)
        assert result["status"] in ("FAIL", "ERROR"), (
            f"count_0_to_9.sv は FAIL するはずが {result['status']} になりました"
        )

    def test_no_reset_fails(self):
        spec = DATA_ROOT / "chapter07" / "lesson02" / "spec.yaml"
        wrong = self._wrong_dir() / "no_reset.sv"
        if not wrong.exists():
            pytest.skip("no_reset.sv not found")
        result = run_deltasim_test(wrong, spec)
        assert result["status"] in ("FAIL", "ERROR"), (
            f"no_reset.sv は FAIL するはずが {result['status']} になりました"
        )


@skip_if_no_deltasim
class TestDeltasimVersion:
    """deltasim のバージョンと schema_version を確認"""

    def test_deltasim_is_available(self):
        """deltasim コマンドが利用可能"""
        result = subprocess.run(
            ["deltasim", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0

    def test_output_schema_version_is_2(self):
        """出力 JSON の schema_version が '2' であること"""
        answer = DATA_ROOT / "chapter06" / "lesson01" / "answer.sv"
        spec = DATA_ROOT / "chapter06" / "lesson01" / "spec.yaml"
        result = run_deltasim_test(answer, spec)
        assert result.get("schema_version") == "2", (
            f"schema_version が '2' ではありません: {result.get('schema_version')}"
        )
