"""
HDL コードの簡易リント機能

deltasim は always_ff 内での = (ブロッキング代入) を警告しないため、
アプリ側で初心者向けのヒントを表示する。

採点失敗にはしない — ヒントのみ。
"""

from __future__ import annotations

import re


def lint_hdl(code: str) -> list[str]:
    """
    SystemVerilog コードを簡易検査し、初心者向けヒントのリストを返す。
    ヒントがない場合は空リストを返す。
    """
    hints: list[str] = []

    # always_ff ブロック内で = (blocking) を使用していないか確認
    hints.extend(_check_blocking_in_ff(code))

    return hints


def _check_blocking_in_ff(code: str) -> list[str]:
    """
    always_ff @(...) begin ... end ブロック内で
    ブロッキング代入 = を使っている行を検出する。

    ヒント: always_ff の中では <= を使う。
    """
    hints: list[str] = []

    # always_ff ブロックを抽出（ネストは考慮しない簡易版）
    ff_block_re = re.compile(
        r"always_ff\s*@\([^)]*\)\s*(?:begin)?(.*?)(?:end\b|$)",
        re.DOTALL | re.IGNORECASE,
    )

    for m in ff_block_re.finditer(code):
        block = m.group(1)
        # ブロック内で = を使っている行（<= ではなく、=）
        for line in block.splitlines():
            stripped = line.strip()
            # コメント行はスキップ
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            # <= は除外して = を検出
            # 条件比較 (==, !=, >=, <=, =>) も除外
            if re.search(r"(?<![<>!])=(?![=>])", stripped):
                if "<=" not in stripped:
                    hints.append(
                        "💡 ヒント: always_ff ブロックの中では = の代わりに <= "
                        "（非ブロッキング代入）を使ってください。\n"
                        f"   該当行: {stripped}\n"
                        "   例: q = d; → q <= d;"
                    )
                    break  # 1ブロックにつき1ヒントで十分

    return hints
