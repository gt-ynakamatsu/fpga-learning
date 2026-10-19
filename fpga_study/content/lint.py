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

    # always_ff ブロック内で = (blocking) を使用していないか確認（複数行版）
    hints.extend(_check_blocking_in_ff(code))
    # 1行の always_ff でも同様に確認
    hints.extend(_check_blocking_in_ff_single(code))

    return hints


def _check_blocking_in_ff(code: str) -> list[str]:
    """
    always_ff @(...) begin ... end ブロック内で
    ブロッキング代入 = を使っている行を検出する。

    ヒント: always_ff の中では <= を使う。
    """
    hints: list[str] = []

    # always_ff ブロックを抽出（begin...end が必要; 1行の always_ff は別処理）
    ff_block_re = re.compile(
        r"always_ff\s*@\([^)]*\)\s*begin(.*?)end\b",
        re.DOTALL | re.IGNORECASE,
    )

    def _strip_line_comments(text: str) -> str:
        """行コメント (//) を除去してから検査する"""
        result = []
        for ln in text.splitlines():
            # // より前の部分のみ使用（文字列リテラル内の // は考慮しない簡易版）
            idx = ln.find("//")
            result.append(ln[:idx] if idx >= 0 else ln)
        return "\n".join(result)

    for m in ff_block_re.finditer(code):
        block = _strip_line_comments(m.group(1))
        # ブロック内で = を使っている行（<= ではなく、=）
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
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


def _check_blocking_in_ff_single(code: str) -> list[str]:
    """
    1行の always_ff（begin...end なし）で = (ブロッキング代入) を検出する。
    例: always_ff @(posedge clk) q = d;
    """
    hints: list[str] = []

    # always_ff @(...) の後に begin なしで直接文が来るケース
    single_ff_re = re.compile(
        r"always_ff\s*@\([^)]*\)\s+(?!begin\b)([^\n;]+;)",
        re.IGNORECASE,
    )

    for m in single_ff_re.finditer(code):
        stmt = m.group(1).strip()
        # // コメントを除去
        idx = stmt.find("//")
        if idx >= 0:
            stmt = stmt[:idx].strip()
        if not stmt:
            continue
        # <= は除外して = を検出（比較演算子 ==, !=, >=, <= も除外）
        if re.search(r"(?<![<>!])=(?![=>])", stmt) and "<=" not in stmt:
            hints.append(
                "💡 ヒント: always_ff ブロックの中では = の代わりに <= "
                "（非ブロッキング代入）を使ってください。\n"
                f"   該当行: {stmt}\n"
                "   例: q = d; → q <= d;"
            )

    return hints
