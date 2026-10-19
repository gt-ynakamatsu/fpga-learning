"""
シミュレータ抽象インターフェース

【設計方針】
- Simulator プロトコルを実装するクラスを差し替えることで、
  将来的に deltasim Python API 連携や実機ボード対応へ移行できる。
- 現バージョンは deltasim CLI を別プロセスで呼び出す薄い連携
  (DeltasimCLISimulator) と、未インストール時のスタブ (StubSimulator) を提供。

【deltasim CLI 呼び出し形式 (docs/api.md §2.2 準拠)】

  deltasim test <RTLファイル...> --spec <仕様YAML> --json <出力パス>
  オプション: --top <モジュール名>  --seed <整数>  --json-events (進捗をJSONLines)

  --json はファイルパスを指定する（stdoutには書き込まれない）。

【出力JSON フォーマット (docs/api.md §2.2 準拠、schema_version "1")】

  {
    "schema_version": "1",          ← バージョン確認必須
    "module":        "counter",
    "status":        "PASS",        ← PASS / FAIL / ERROR / SKIP
    "seed":          42,
    "elapsed_ms":    12.3,
    "cancelled":     false,
    "log":           [],
    "checks": [
      {
        "name":       "count@cycle11[spec]",
        "status":     "PASS",       ← PASS / FAIL / ERROR / SKIP
        "signal":     "count",
        "cycle":      11,
        "time_ns":    110,
        "expected":   "00000001",   ← 4値文字列(0/1/x/z)、MSB先頭
        "actual":     "00000001",
        "source":     "spec",
        "seed":       42,
        "elapsed_ms": 0.5,
        "message":    null
      }
    ],
    "errors": [
      {
        "file":     "counter.sv",
        "line":     5,
        "column":   3,
        "severity": "error",
        "message":  "expected ';', got '?'",
        "code":     "E001"
      }
    ]
  }

【近日変更予定（互換のため未知フィールドは無視する）】
  - テストケース単位の集計フィールド追加
  - summary.elapsed_ms 追加
  - Z 値を小文字 "z" で X ("x") と区別

【利用するフィールドは status / checks / errors のみ】
  schema_version を確認し、非対応バージョンは初心者向け案内を出す。
  パーサは _parse_deltasim_result() に一元化。

【将来の拡張ポイント】
  - DeltasimPythonAPISimulator: deltasim Python API (ds.test()) を直接呼ぶ
  - BoardSimulator: 実機ボード対応
  factory 関数 get_default_simulator() でクラスを切り替える。
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

SUPPORTED_SCHEMA_VERSION = "1"


@dataclass
class CheckResult:
    """1件のチェック結果 (checks[] の要素)"""
    name: str
    status: str           # "PASS" / "FAIL" / "ERROR" / "SKIP"
    signal: str
    cycle: int
    time_ns: int
    expected: str         # 4値文字列 (MSB先頭)
    actual: str           # 4値文字列 (MSB先頭)
    message: Optional[str] = None


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
    """シミュレーション結果 (test() / deltasim test --json の構造に対応)"""
    success: bool
    status: str = "ERROR"  # "PASS" / "FAIL" / "ERROR" / "SKIP"
    checks: list[CheckResult] = field(default_factory=list)
    errors: list[ErrorDetail] = field(default_factory=list)
    raw_output: str = ""
    user_message: str = ""
    """初心者向けのわかりやすいメッセージ"""


@runtime_checkable
class Simulator(Protocol):
    """シミュレータの共通インターフェース (Protocolクラス)"""

    def run(
        self,
        rtl_files: list[Path],
        spec_yaml: Path,
        top: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> SimulationResult:
        """RTLファイルと仕様YAMLを受け取りシミュレーションを実行する"""
        ...

    def is_available(self) -> bool:
        """シミュレータが利用可能かどうかを返す"""
        ...


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
    deltasim CLI (`deltasim test <files> --spec <yaml> --json <out>`) を
    別プロセスで呼び出す薄い連携クラス。

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
            json_out = Path(tmp) / "result.json"

            cmd: list[str] = ["deltasim", "test"]
            cmd += [str(f) for f in rtl_files]
            cmd += ["--spec", str(spec_yaml)]
            cmd += ["--json", str(json_out)]
            if top:
                cmd += ["--top", top]
            if seed is not None:
                cmd += ["--seed", str(seed)]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                )
                raw = json_out.read_text(encoding="utf-8") if json_out.exists() else ""
                return _parse_deltasim_result(raw)
            except subprocess.TimeoutExpired:
                return SimulationResult(
                    success=False,
                    status="ERROR",
                    user_message=(
                        "⏱️ シミュレーションが時間内に終わりませんでした。\n"
                        "コードに無限ループがないか確認してみましょう。"
                    ),
                )
            except Exception as exc:
                return SimulationResult(
                    success=False,
                    status="ERROR",
                    user_message=_friendly_error(str(exc)),
                )


def _parse_deltasim_result(raw: str) -> SimulationResult:
    """
    deltasim CLI の --json 出力ファイルをパースする。
    【フォーマット仕様】は simulator.py モジュール冒頭を参照。

    利用するフィールドは status / checks / errors のみ。
    未知のフィールドは無視する。schema_version を確認し、
    非対応バージョンは初心者向け案内を表示する。

    ⚠️ フォーマット変更時はここだけ修正すること。
    """
    if not raw.strip():
        return SimulationResult(
            success=False,
            status="ERROR",
            raw_output=raw,
            user_message="❌ シミュレーション結果が空でした。deltasimが正常に実行されたか確認してください。",
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
    if schema_ver != SUPPORTED_SCHEMA_VERSION:
        return SimulationResult(
            success=False,
            status="ERROR",
            raw_output=raw,
            user_message=(
                f"⚠️ シミュレータのバージョンが対応していません "
                f"(schema_version={schema_ver!r}, 対応: {SUPPORTED_SCHEMA_VERSION!r})。\n"
                "アプリを最新版に更新してください。"
            ),
        )

    status = data.get("status", "ERROR")
    success = status == "PASS"

    checks: list[CheckResult] = []
    for c in data.get("checks", []):
        checks.append(CheckResult(
            name=c.get("name", ""),
            status=c.get("status", "ERROR"),
            signal=c.get("signal", ""),
            cycle=c.get("cycle", 0),
            time_ns=c.get("time_ns", 0),
            expected=c.get("expected", ""),
            actual=c.get("actual", ""),
            message=c.get("message"),
        ))

    errors: list[ErrorDetail] = []
    for e in data.get("errors", []):
        errors.append(ErrorDetail(
            file=e.get("file", ""),
            line=e.get("line", 0),
            column=e.get("column", 0),
            severity=e.get("severity", "error"),
            message=e.get("message", ""),
            code=e.get("code", ""),
        ))

    user_message = _build_user_message(success, status, checks, errors)

    return SimulationResult(
        success=success,
        status=status,
        checks=checks,
        errors=errors,
        raw_output=raw,
        user_message=user_message,
    )


def _build_user_message(
    success: bool,
    status: str,
    checks: list[CheckResult],
    errors: list[ErrorDetail],
) -> str:
    if success:
        return f"✅ テスト合格！ ({len(checks)}件全て通過)"

    if status == "SKIP":
        return "⏭️ テストはスキップされました。"

    lines: list[str] = []

    if errors:
        lines.append("❌ コードにエラーが見つかりました：")
        for e in errors[:5]:
            loc = f"{e.file}:{e.line}:{e.column}" if e.file else f"行{e.line}"
            lines.append(f"  [{e.severity}] {loc} — {_friendly_error(e.message)}")
        if len(errors) > 5:
            lines.append(f"  （他 {len(errors) - 5} 件）")
    elif status == "FAIL":
        failed = [c for c in checks if c.status != "PASS"]
        lines.append(f"❌ {len(failed)}件のチェックが不合格です：")
        for c in failed[:5]:
            lines.append(
                f"  {c.signal} (サイクル{c.cycle}): 期待={c.expected} / 実際={c.actual}"
            )
        if len(failed) > 5:
            lines.append(f"  （他 {len(failed) - 5} 件）")
    else:
        lines.append(f"❌ シミュレーションに失敗しました (status={status})。")

    return "\n".join(lines)


def _friendly_error(message: str) -> str:
    """
    エラーメッセージを初心者向けに言い換える。
    技術的なキーワードを検知して補足説明を付ける。
    """
    lower = message.lower()
    hints = [
        ("syntax error",      "書き方のミスがあります（文法エラー）"),
        ("expected ';'",      "セミコロン ';' が抜けています"),
        ("undeclared",        "宣言されていない信号や変数を使っています"),
        ("undefined",         "定義されていないものを参照しています"),
        ("timeout",           "処理が時間内に終わりませんでした"),
        ("connection refused","シミュレータに接続できませんでした"),
        ("multiple drivers",  "複数の箇所から同じ信号を制御しています"),
    ]
    for keyword, friendly in hints:
        if keyword in lower:
            return f"{friendly}（詳細: {message}）"
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
