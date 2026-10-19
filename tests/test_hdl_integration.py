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
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

DATA_ROOT = Path(__file__).parent.parent / "fpga_study" / "data"

DELTASIM_AVAILABLE = shutil.which("deltasim") is not None


# ── §15 (offset_ns) サポートチェック ─────────────────────────────────


def _probe_offset_ns_support() -> bool:
    """
    deltasim が §15 offset_ns を正しく処理するかプローブする。
    古い deltasim は offset_ns を無視して PASS を返す（誤検知の原因）。
    → at:2 offset_ns:6 で D=1 を設定し、at:2 check で Q=0 が期待される。
    Q=1 なら offset_ns は無視されている（§15 未対応）。
    """
    if not DELTASIM_AVAILABLE:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        sv = Path(tmp) / "probe.sv"
        sv.write_text(
            "module probe_dff(input logic clk, input logic d, output logic q);\n"
            "    always_ff @(posedge clk) q <= d;\n"
            "endmodule\n"
        )
        spec = Path(tmp) / "probe.yaml"
        spec.write_text(
            "version: 1\ntop: probe_dff\n"
            "clock: {signal: clk, period_ns: 10}\nsim: {cycles: 5}\n"
            "cases:\n"
            "  - name: offset_probe\n"
            "    inputs:\n"
            "      - {at: 2, offset_ns: 6, set: {d: 1}}\n"
            "    expected:\n"
            "      - {at: 2, check: {q: 0}}\n"  # §15 対応なら q=0（edgeではまだd=0）
        )
        json_out = Path(tmp) / "r.json"
        result = subprocess.run(
            ["deltasim", "test", str(sv), "--spec", str(spec), "--json", str(json_out)],
            capture_output=True, text=True, timeout=10,
        )
        if not json_out.exists():
            return False
        data = json.loads(json_out.read_text())
        # PASS = offset_ns が正しく動作している（D=1 設定はエッジ後なので q=0）
        return data.get("status") == "PASS"


OFFSET_NS_SUPPORTED = _probe_offset_ns_support()

skip_if_no_deltasim = pytest.mark.skipif(
    not DELTASIM_AVAILABLE,
    reason="deltasim がインストールされていません（pip install deltasim）",
)

require_offset_ns = pytest.mark.skipif(
    not OFFSET_NS_SUPPORTED,
    reason=(
        "⚠️ この deltasim は §15 (offset_ns) に対応していません。"
        " b482527 以降をインストールしてください: "
        "pip install git+https://github.com/gt-ynakamatsu/deltasim.git@b482527"
        " offset_ns が無効な旧バージョンでは誤った PASS になる可能性があるため"
        " このテストは SKIP されます（silent PASS 禁止）。"
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


@skip_if_no_deltasim
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


@skip_if_no_deltasim
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


@skip_if_no_deltasim
class TestOffsetNsSupport:
    """§15 サポートの確認（このテストが FAIL なら古い deltasim を使用中）"""

    def test_offset_ns_is_supported(self):
        """
        offset_ns が正しく動作することを確認する。
        FAIL した場合: deltasim b482527 以降をインストールしてください。
        pip install git+https://github.com/gt-ynakamatsu/deltasim.git@b482527
        """
        assert OFFSET_NS_SUPPORTED, (
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


@skip_if_no_deltasim
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
        if filename in _OFFSET_NS_REQUIRED_FILES and not OFFSET_NS_SUPPORTED:
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


@skip_if_no_deltasim
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
