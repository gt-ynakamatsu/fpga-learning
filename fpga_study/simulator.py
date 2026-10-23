"""
シミュレータ抽象インターフェース

【設計方針】
- Simulator プロトコルを実装するクラスを差し替えることで、
  将来的に deltasim Python API 連携や実機ボード対応へ移行できる。
- 現バージョンは deltasim CLI を別プロセスで呼び出す薄い連携
  (DeltasimCLISimulator) と、未インストール時のスタブ (StubSimulator) を提供。

【deltasim CLI 呼び出し形式 (docs/api.md §2.2 準拠)】

  deltasim test <RTLファイル...> --spec <仕様YAML> --json <出力パス>
  オプション: --top <モジュール名>  --seed <整数>
              --record all          (全信号記録; 旧 --record-all は非推奨)
              --wave-mem <MB>       (波形メモリ上限 MB)
              --case <パターン>      (fnmatch ワイルドカード対応、複数指定可)
              --json-events         (進捗をJSON Linesでstdoutへ、現バージョン未使用)

  --json はファイルパスを指定する（stdoutではない）。

【出力JSON フォーマット (docs/api.md §2.2 / §13.2 準拠、schema_version "2")】

  {
    "schema_version": "2",           ← メジャー番号が変わったときだけ警告
    "module":        "counter",
    "status":        "PASS",         ← PASS / FAIL / ERROR / SKIP
    "seed":          42,
    "elapsed_ms":    50.3,           ← 非推奨。summary.elapsed_ms と同値
    "summary": {"elapsed_ms": 50.3}, ← 全体実行時間（推奨）
    "cancelled":     false,
    "log":           [],
    "cases": [                       ← テストケースごとの結果（新規）
      {
        "name":       "basic",
        "status":     "PASS",
        "seed":       42,
        "elapsed_ms": 12.3,
        "message":    null,
        "checks": [
          {
            "name":       "count@cycle11[spec]",
            "status":     "PASS",
            "signal":     "count",
            "cycle":      11,
            "time_ns":    110,
            "expected":   "00000001",  ← 4値文字列(0/1/x/z)、MSB先頭、小文字
            "actual":     "00000001",
            "source":     "spec",
            "seed":       42,
            "elapsed_ms": 0.5,
            "message":    null
          }
        ],
        "log": []
      }
    ],
    "checks": [...],   ← 全ケース集計（後方互換）
    "errors": []
  }

【schema_version バージョン確認方針】
  メジャーバージョン（先頭の数字、"." より前の部分）が異なる場合のみ警告。
  "2" と "2.1" は同じメジャーなので互換。"3" は非互換として案内を出す。

【近日変更予定への対応】
  - cases[].message フィールド追加済み
  - truncated_at（波形記録停止時刻）は無視
  - 未知フィールドは常に無視する

【E_NO_CASE エラー (docs/api.md §14.1)】
  --case フィルタがいずれのケースにも一致しない場合:
  status="ERROR", cases=[], errors=[{code:"E_NO_CASE", ...}]
  初心者向けメッセージを表示する。

【利用するフィールド】
  status / cases / checks / errors / summary.elapsed_ms
  パーサは _parse_deltasim_result() に一元化。フォーマット変更時はここだけ修正。

【将来の拡張ポイント】
  DeltasimPythonAPISimulator : deltasim Python API (ds.test()) 直接呼び出し
  BoardSimulator             : 実機ボード対応
  get_default_simulator() で切り替える。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

SUPPORTED_SCHEMA_MAJOR = "2"

# deltasim 最低バージョン要件（v0.2.2 以上が必須）
DELTASIM_MIN_VERSION = "0.2.2"


def get_deltasim_version() -> Optional[str]:
    """インストール済み deltasim のバージョン文字列を返す。未インストールなら None。"""
    try:
        result = subprocess.run(
            ["deltasim", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", result.stdout)
        return m.group(1) if m else None
    except Exception:
        return None


def _version_tuple(v: str) -> tuple:
    """バージョン文字列をセマンティック比較用タプルに変換"""
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)




def check_deltasim_requirement(
    min_version: str = DELTASIM_MIN_VERSION,
) -> tuple:
    """
    deltasim が要件を満たすかを確認する。
    戻り値: (ok: bool, version: str|None, message: str)

    `deltasim --version` からバージョンを取得し、セマンティックに比較する。
    result JSON の `deltasim_version` フィールドも使って実行時に二重確認できる
    （_parse_deltasim_result 内で自動確認）。
    0.2.2 未満の場合はグレーディングを拒否し、統合テストは SKIP する。
    """
    install_hint = "pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@v0.2.2'"

    ver = get_deltasim_version()
    if ver is None:
        return (
            False, None,
            f"deltasim がインストールされていません。\nインストール: {install_hint}",
        )

    if _version_tuple(ver) >= _version_tuple(min_version):
        return (True, ver, ver)

    return (
        False, ver,
        f"deltasim {min_version} 以上が必要です（現在: {ver}）。\n"
        f"アップグレード: {install_hint}",
    )


# ── データクラス ────────────────────────────────────────────────────────


@dataclass
class WarningDetail:
    """結果JSON の warnings[] の要素 (§15.12 W_UNKNOWN_KEY など)"""
    code: str
    message: str


@dataclass
class CheckResult:
    """1件のチェック結果 (checks[] の要素)"""
    name: str
    status: str           # "PASS" / "FAIL" / "ERROR" / "SKIP"
    signal: str
    cycle: int
    time_ns: int
    expected: str         # 4値文字列 (MSB先頭、小文字)
    actual: str
    message: Optional[str] = None
    offset_ns: int = 0    # サイクル内オフセット (v0.2.2+、§15.7)


@dataclass
class CaseResult:
    """テストケース1件の結果 (cases[] の要素、docs/api.md §13.2)"""
    name: str
    status: str           # "PASS" / "FAIL" / "ERROR" / "SKIP"
    seed: Optional[int]
    elapsed_ms: float
    checks: list[CheckResult] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    message: Optional[str] = None
    case_errors: list["ErrorDetail"] = field(default_factory=list)  # cases[].errors (v0.2.2+)


@dataclass
class ErrorDetail:
    """構造化エラー (errors[] の要素)"""
    file: str
    line: int
    column: int
    severity: str         # "error" / "warning"
    message: str
    code: str


@dataclass
class SimulationResult:
    """
    シミュレーション結果。
    test() の戻り値 / deltasim test --json の構造に対応。
    """
    success: bool
    status: str = "ERROR"   # "PASS" / "FAIL" / "ERROR" / "SKIP"
    cases: list[CaseResult] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    errors: list[ErrorDetail] = field(default_factory=list)
    warnings: list[WarningDetail] = field(default_factory=list)
    deltasim_version: Optional[str] = None       # result JSON の deltasim_version
    summary_elapsed_ms: Optional[float] = None   # summary.elapsed_ms（推奨）
    raw_output: str = ""
    user_message: str = ""
    """初心者向けのわかりやすいメッセージ"""


# ── Simulator プロトコル ─────────────────────────────────────────────────


@runtime_checkable
class Simulator(Protocol):
    """シミュレータの共通インターフェース (Protocol クラス)"""

    def run(
        self,
        rtl_files: list[Path],
        spec_yaml: Path,
        top: Optional[str] = None,
        seed: Optional[int] = None,
        record_all: bool = False,
        wave_mem_mb: Optional[int] = None,
        filter_cases: Optional[list[str]] = None,
    ) -> SimulationResult:
        """RTLファイルと仕様YAMLを受け取りシミュレーションを実行する"""
        ...

    def is_available(self) -> bool:
        """シミュレータが利用可能かどうかを返す"""
        ...


# ── 実装クラス ──────────────────────────────────────────────────────────


class StubSimulator:
    """
    開発用スタブ。
    deltasim が未インストール／HDL演習が未実装のときに使う。
    """

    def run(
        self,
        rtl_files: list[Path],
        spec_yaml: Path,
        top: Optional[str] = None,
        seed: Optional[int] = None,
        record_all: bool = False,
        wave_mem_mb: Optional[int] = None,
        filter_cases: Optional[list[str]] = None,
    ) -> SimulationResult:
        return SimulationResult(
            success=False,
            status="SKIP",
            user_message=(
                "⚠️ HDLシミュレーション機能は現在準備中です。\n"
                "第1・2章の回路パズルは今すぐ遊べます！"
            ),
        )

    def is_available(self) -> bool:
        return False


class DeltasimCLISimulator:
    """
    deltasim CLI を別プロセスで呼び出す薄い連携クラス。

    deltasim がインストールされていない環境では is_available() が False を返し、
    run() は初心者向けメッセージを含む失敗結果を返す（例外は発生しない）。

    将来的に Python API 連携に移行する場合は、このクラスを差し替えるか、
    新たに DeltasimPythonAPISimulator を実装して get_default_simulator() で切り替える。
    """

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                ["deltasim", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def run(
        self,
        rtl_files: list[Path],
        spec_yaml: Path,
        top: Optional[str] = None,
        seed: Optional[int] = None,
        record_all: bool = False,
        wave_mem_mb: Optional[int] = None,
        filter_cases: Optional[list[str]] = None,
    ) -> SimulationResult:
        if not self.is_available():
            return SimulationResult(
                success=False,
                status="ERROR",
                user_message=(
                    "⚠️ HDLシミュレータ (deltasim) がインストールされていません。\n"
                    "インストール方法: pip install deltasim\n"
                    "第1・2章の回路パズルは deltasim なしで遊べます。"
                ),
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            json_out = tmp_path / "result.json"

            # §11-27: cwd を一時フォルダにする → deltasim.log が一時フォルダ内に生成され、
            #         TemporaryDirectory 削除と同時に消える。呼び出し元の CWD を汚さない。
            #         cwd を変えてもパス解決が壊れないよう、ファイルパスはすべて絶対パスで渡す。
            abs_rtl_files = [Path(f).resolve() for f in rtl_files]
            abs_spec_yaml = Path(spec_yaml).resolve()
            abs_json_out = json_out.resolve()

            cmd: list[str] = ["deltasim", "test"]
            cmd += [str(f) for f in abs_rtl_files]
            cmd += ["--spec", str(abs_spec_yaml)]
            cmd += ["--json", str(abs_json_out)]
            if top:
                cmd += ["--top", top]
            if seed is not None:
                cmd += ["--seed", str(seed)]
            if record_all:
                cmd += ["--record", "all"]   # 旧 --record-all は非推奨
            if wave_mem_mb is not None:
                cmd += ["--wave-mem", str(wave_mem_mb)]
            if filter_cases:
                for case_name in filter_cases:
                    cmd += ["--case", case_name]

            try:
                _env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self._timeout,
                    env=_env,
                    cwd=tmp,
                )
                raw = json_out.read_text(encoding="utf-8") if json_out.exists() else ""
                stderr = proc.stderr or ""
                return _parse_deltasim_result(raw, stderr, spec_yaml=abs_spec_yaml)
            except subprocess.TimeoutExpired:
                return SimulationResult(
                    success=False,
                    status="ERROR",
                    user_message=(
                        "⏱️ シミュレーションが時間内に終わりませんでした。\n"
                        "無限ループ、または文法の間違い（endmodule の書き忘れなど）がないか確認してください。"
                    ),
                )
            except Exception as exc:
                return SimulationResult(
                    success=False,
                    status="ERROR",
                    user_message=_friendly_error(str(exc)),
                )


# ── パーサ（一元化） ─────────────────────────────────────────────────────


def _get_spec_top_module(spec_yaml: Optional[Path]) -> Optional[str]:
    """spec.yaml の top フィールドを返す（取得失敗時は None）。"""
    if spec_yaml is None:
        return None
    try:
        import yaml as _yaml
        data = _yaml.safe_load(Path(spec_yaml).read_text(encoding="utf-8"))
        return data.get("top") if isinstance(data, dict) else None
    except Exception:
        return None


def _parse_deltasim_result(
    raw: str,
    stderr: str = "",
    spec_yaml: Optional[Path] = None,
) -> SimulationResult:
    """
    deltasim CLI の --json 出力ファイルをパースする。
    【フォーマット仕様】は simulator.py モジュール冒頭を参照。

    利用するフィールド: status / cases / checks / errors / summary.elapsed_ms
    未知のフィールドは無視する。
    schema_version のメジャー番号が異なる場合のみ警告を表示する。

    ⚠️ フォーマット変更時はここだけ修正すること。
    """
    if not raw.strip():
        # JSON が出なかった = 想定外の異常終了 (E_INTERNAL 扱い)
        return SimulationResult(
            success=False,
            status="ERROR",
            raw_output=stderr or raw,
            user_message=(
                "⚠️ 採点ツールの不具合の可能性があります。\n"
                "再度お試しください。繰り返し発生する場合は担当者にご報告ください。"
            ),
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return SimulationResult(
            success=False,
            status="ERROR",
            raw_output=raw,
            user_message=f"❌ シミュレーション結果の読み取りに失敗しました。\n詳細: {exc}",
        )

    schema_ver = str(data.get("schema_version", ""))
    compat_warning = _check_schema_compat(schema_ver)
    if compat_warning:
        return SimulationResult(
            success=False,
            status="ERROR",
            raw_output=raw,
            user_message=compat_warning,
        )

    # result JSON の deltasim_version を取得
    result_deltasim_version: Optional[str] = data.get("deltasim_version")

    status = data.get("status", "ERROR")
    success = status == "PASS"

    summary = data.get("summary") or {}
    summary_elapsed_ms: Optional[float] = summary.get("elapsed_ms")

    cases: list[CaseResult] = []
    for c in data.get("cases", []):
        cases.append(_parse_case(c))

    checks: list[CheckResult] = [_parse_check(c) for c in data.get("checks", [])]

    errors: list[ErrorDetail] = [_parse_error(e) for e in data.get("errors", [])]

    # §15.12: warnings は常に存在する（v0.2.2 以降は常に空リストまたはリスト）
    # 旧バージョン互換のため None または absent の場合も空リストとして扱う
    raw_warnings = data.get("warnings") or []
    warnings: list[WarningDetail] = [_parse_warning(w) for w in raw_warnings]

    spec_top = _get_spec_top_module(spec_yaml)
    user_message = _build_user_message(success, status, cases, checks, errors, warnings, spec_top=spec_top)

    return SimulationResult(
        success=success,
        status=status,
        cases=cases,
        checks=checks,
        errors=errors,
        warnings=warnings,
        deltasim_version=result_deltasim_version,
        summary_elapsed_ms=summary_elapsed_ms,
        raw_output=raw,
        user_message=user_message,
    )


def _parse_case(c: dict) -> "CaseResult":
    return CaseResult(
        name=c.get("name", ""),
        status=c.get("status", "ERROR"),
        seed=c.get("seed"),
        elapsed_ms=float(c.get("elapsed_ms", 0.0)),
        checks=[_parse_check(ch) for ch in c.get("checks", [])],
        log=list(c.get("log", [])),
        message=c.get("message"),
        case_errors=[_parse_error(e) for e in c.get("errors", [])],  # v0.2.2+
    )


def _parse_check(c: dict) -> CheckResult:
    return CheckResult(
        name=c.get("name", ""),
        status=c.get("status", "ERROR"),
        signal=c.get("signal", ""),
        cycle=c.get("cycle", 0),
        time_ns=c.get("time_ns", 0),
        expected=c.get("expected", ""),
        actual=c.get("actual", ""),
        message=c.get("message"),
        offset_ns=int(c.get("offset_ns") or 0),  # v0.2.2+ §15.7
    )


def _parse_warning(w: dict) -> WarningDetail:
    return WarningDetail(
        code=w.get("code", ""),
        message=w.get("message", ""),
    )


def _parse_error(e: dict) -> ErrorDetail:
    return ErrorDetail(
        file=e.get("file", ""),
        line=e.get("line", 0),
        column=e.get("column", 0),
        severity=e.get("severity", "error"),
        message=e.get("message", ""),
        code=e.get("code", ""),
    )


def _check_schema_compat(schema_ver: str) -> Optional[str]:
    """
    メジャーバージョン（"." 前の数字）が一致するかチェックする。
    不一致の場合は初心者向けメッセージを返す。
    """
    actual_major = str(schema_ver).split(".")[0] if schema_ver else ""
    if actual_major != SUPPORTED_SCHEMA_MAJOR:
        return (
            f"⚠️ シミュレータの結果バージョンが対応していません "
            f"(schema_version={schema_ver!r}, 対応メジャー: {SUPPORTED_SCHEMA_MAJOR})。\n"
            "アプリを最新版に更新してください。"
        )
    return None


_LOOP_CODES = {"E_DELTA_LIMIT", "E_LOOP_LIMIT"}
_INTERNAL_CODES = {"E_INTERNAL"}


# ── §11-29: 4値論理 x/z ヒント ──────────────────────────────────────────────

def _detect_xz_in_checks(
    cases: "list[CaseResult]",
    checks: "list[CheckResult]",
) -> "tuple[bool, bool]":
    """失敗チェックの actual に x または z が含まれるかを返す。

    deltasim ea48e9d+ の 4 値論理で、未初期化 FF は x、未駆動出力は z を返す。
    v0.2.2 / v0.3.0 の出力は 0/1 のみなので has_x=has_z=False となり、
    v0.2.2 との後方互換性が自然に保たれる。

    Returns:
        (has_x, has_z)
    """
    has_x = False
    has_z = False
    # cases[].checks[] を走査
    for case in cases:
        for ch in case.checks:
            if ch.status == "PASS":
                continue
            actual = ch.actual or ""
            if "x" in actual:
                has_x = True
            if "z" in actual:
                has_z = True
    # トップレベル checks[] も走査（レガシーパス）
    for ch in checks:
        if ch.status == "PASS":
            continue
        actual = ch.actual or ""
        if "x" in actual:
            has_x = True
        if "z" in actual:
            has_z = True
    return has_x, has_z


def _xz_hint_lines(has_x: bool, has_z: bool) -> "list[str]":
    """§11-29: x/z 検出時のヒント文を返す（x が先）。各 1 件ずつ。"""
    lines: list[str] = []
    if has_x:
        lines.append("x は値がまだ決まっていない状態です。リセットで初期値を入れているか確認しましょう")
    if has_z:
        lines.append("z はどこからも値が入っていない状態です。出力に値を代入しているか確認しましょう")
    return lines


def _classify_errors(
    errors: list[ErrorDetail],
    cases: list["CaseResult"],
) -> Optional[str]:
    """
    errors[] と cases[].errors の code を見て初心者向けメッセージを返す。
    分類できなければ None。
    """
    all_codes = {e.code for e in errors}
    for c in cases:
        all_codes.update(e.code for e in getattr(c, "case_errors", []))

    if all_codes & _LOOP_CODES:
        return (
            "⚠️ 回路が終わらない書き方（組み合わせのループや無限ループ）の可能性があります。\n"
            "コードを見直してください。\n"
            "（例：`assign y = ~y;` のような自己参照は動きません）"
        )
    if all_codes & _INTERNAL_CODES:
        return (
            "⚠️ 採点ツールの不具合の可能性があります。\n"
            "再度お試しください。繰り返し発生する場合は担当者にご報告ください。"
        )
    return None


def _build_user_message(
    success: bool,
    status: str,
    cases: list[CaseResult],
    checks: list[CheckResult],
    errors: list[ErrorDetail],
    warnings: Optional[list[WarningDetail]] = None,
    spec_top: Optional[str] = None,
) -> str:
    if status == "SKIP":
        return "⏭️ テストはスキップされました。"

    # エラーコードによる分類（keywords ではなく code で判定）
    loop_or_internal = _classify_errors(errors, cases)
    if loop_or_internal:
        return loop_or_internal

    # §15.12: W_UNKNOWN_KEY などのワーニングを表示（非致命的）
    warning_lines: list[str] = []
    for w in (warnings or []):
        if w.code == "W_UNKNOWN_KEY":
            warning_lines.append(f"⚠️ 仕様YAML に不明なキーがあります（無視されます）: {w.message}")
        else:
            warning_lines.append(f"⚠️ [{w.code}] {w.message}")

    # E_NO_CASE: --case フィルタがどのケースにも一致しなかった
    for e in errors:
        if e.code == "E_NO_CASE":
            pattern = e.message or ""
            return (
                "⚠️ 指定したケース名がどのテストケースにも一致しませんでした。\n"
                f"指定パターン: {pattern}\n"
                "ケース名（YAML の cases[].name）を確認してください。"
            )

    if success:
        case_summary = ""
        if cases:
            case_summary = f" ({len(cases)}ケース全て通過)"
        msg = f"✅ テスト合格！{case_summary}"
        if warning_lines:
            msg = "\n".join(warning_lines) + "\n" + msg
        return msg

    lines: list[str] = []

    if errors:
        lines.append("❌ コードにエラーが見つかりました：")
        seen_codes: set = set()
        shown = 0
        for e in errors:
            # 同じコードのエラーは1件にまとめる
            dedup_key = (e.code, e.message[:60])
            if dedup_key in seen_codes:
                continue
            seen_codes.add(dedup_key)
            # E001: §11.20 の見出し形式
            if e.code == "E001":
                lines.append(f"  {_format_e001(e)}")
            else:
                # ファイル名のみ（/tmp パスを除去）
                fname = Path(e.file).name if e.file else ""
                loc = f"{fname}:{e.line}" if fname else (f"行{e.line}" if e.line else "")
                lines.append(f"  [{e.severity}]{(' ' + loc) if loc else ''} — {_friendly_error(e.message, e.code, spec_top=spec_top)}")
            shown += 1
            if shown >= 5:
                break
    elif cases:
        failed_cases = [c for c in cases if c.status not in ("PASS", "SKIP")]
        lines.append(f"❌ {len(failed_cases)}ケースが不合格です。")
        # 詳細はフロントエンドのケース別表示に任せる（英語ケース名・ns情報は app.js で処理）
        # §11-29: x/z ヒント（各1件のみ）
        has_x, has_z = _detect_xz_in_checks(cases, [])
        lines.extend(_xz_hint_lines(has_x, has_z))
    elif status == "FAIL":
        failed = [c for c in checks if c.status != "PASS"]
        lines.append(f"❌ {len(failed)}件のチェックが不合格です：")
        for c in failed[:5]:
            lines.append(
                f"  {c.signal} (サイクル{c.cycle}): "
                f"期待={c.expected} / 実際={c.actual}"
            )
        if len(failed) > 5:
            lines.append(f"  （他 {len(failed) - 5} 件）")
        # §11-29: x/z ヒント（各1件のみ）
        has_x, has_z = _detect_xz_in_checks([], checks)
        lines.extend(_xz_hint_lines(has_x, has_z))
    else:
        lines.append(f"❌ シミュレーションに失敗しました (status={status})。")

    if warning_lines:
        lines = warning_lines + lines
    return "\n".join(lines)



def _format_e001(e: "ErrorDetail") -> str:
    """
    E001 エラーを §11.20 の仕様で日本語の見出しに変換する。
    - §11.17 に当てはまる場合はその専用見出し
    - それ以外は「書き方にまちがいがあります（N行目）」 + 問題内容
    """
    msg = e.message
    lower = msg.lower()
    line_str = f"（{e.line}行目）" if e.line else ""

    # §11.17 固有パターン
    if "top module" in lower and "not found" in lower:
        return f"モジュール名が違います"
    if "expected port direction" in lower:
        return f"ポートの向き（input / output / inout）が指定されていません{line_str}"

    # 汎用 E001：見出し + 問題内容（§11.22: 英語原文は「詳細」欄のみ）
    jp_detail = _friendly_error(msg, "E001")
    result = f"書き方にまちがいがあります{line_str}"
    if jp_detail and jp_detail != msg:
        # _friendly_error で日本語に変換できた場合のみ見出し直下に表示
        result += f"\n  → {jp_detail}"
    elif msg and any(ord(c) > 0x3000 for c in msg):
        # deltasim v0.2.2+ が返す日本語メッセージはそのまま表示
        result += f"\n  → {msg}"
    # else: 英語原文は error_detail（「詳細」欄）にのみ入る
    return result


def _friendly_error(message: str, code: str = "", spec_top: Optional[str] = None) -> str:
    """
    エラーメッセージを初心者向けに言い換える。
    可能な限り code で判定。code だけで区別できないものは message で判定。
    """
    import re as _re
    message = _re.sub(r'/tmp/[^\s:,)]+', 'design.sv', message)
    lower = message.lower()

    # §11-28: 新エラーコード
    if code == "E_AMBIGUOUS_TOP":
        if spec_top:
            return f"モジュールが2つ以上あります。課題で指定されたモジュール（`{spec_top}`）を1つだけ書いてください"
        return "モジュールが2つ以上あります。課題で指定されたモジュールを1つだけ書いてください"
    if code in ("E_UNKNOWN_PORT", "E_NO_CHECK"):
        return "採点の設定に問題があります。あなたのコードのせいではありません（教材の不具合です）"

    if code == "E002":
        return "モジュール名が違います"
    if code == "E_DELTA_LIMIT":
        return "組み合わせのループがあります（assign y = ~y; のような自己参照）"
    if code == "E_LOOP_LIMIT":
        return "繰り返しが終わらないコード（while ループが上限を超えました）"
    if code == "E_INTERNAL":
        return "採点ツールの内部エラーが発生しました"
    if "expected port direction" in message:
        return "ポートの向き（input / output / inout）が指定されていません"
    if "top module" in lower and "not found" in lower:
        return "モジュール名が違います"
    # E001 ですでに日本語のメッセージ（deltasim v0.2.2+）はそのまま使う
    if "ありません" in message or "見つかりません" in message or "開始" in message:
        return message

    # よくある E001 パターン（§11.20 の2行目に使う日本語）
    # セミコロン抜け: expected ';' … を最初にチェック（endmodule 判定より優先）
    if "expected ';'" in message:
        return "セミコロン ';' が抜けています"
    # カンマ抜け: expected ')' got 'output' など（ポートリスト内の識別子）
    if "expected ')'" in message and "got '" in message:
        got = message.split("got '")[-1].split("'")[0] if "got '" in message else ""
        if got in ("output", "input", "inout", "logic", "reg", "wire"):
            return "「,」（カンマ）が抜けています"
        return "「)」が足りません"
    # end 抜け: expected token type ID, got KW ('endmodule') など
    if ("got kw" in lower or "got keyword" in lower) and "endmodule" in lower:
        return "「end」が足りません"
    if "expected" in lower and "endmodule" in lower:
        return "「end」が足りません"
    # module なし: No module declaration found
    if "no module" in lower:
        return "module がありません"
    # 式が途中で終わっている: unexpected token in expression
    if "unexpected token in expression" in lower or "unexpected token: ';'" in lower:
        return "式の途中で終わっています（= の後ろに値が必要です）"

    hints = [
        ("syntax error",    "書き方のミスがあります（文法エラー）"),
        ("undeclared",      "宣言されていない信号や変数を使っています"),
        ("undefined",       "定義されていないものを参照しています"),
        ("multiple drivers","複数の箇所から同じ信号を制御しています"),
    ]
    for keyword, friendly in hints:
        if keyword in lower:
            return friendly
    return message


def get_default_simulator() -> Simulator:
    """
    環境に応じて適切なシミュレータを返すファクトリ関数。
    deltasim がインストール済みなら CLI 版を、そうでなければスタブを返す。

    将来的に Python API 版や実機ボード対応版に切り替える場合はここを変更する。
    """
    cli = DeltasimCLISimulator()
    if cli.is_available():
        return cli
    return StubSimulator()
