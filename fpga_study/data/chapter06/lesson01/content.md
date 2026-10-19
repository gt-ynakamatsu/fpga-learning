# module と assign — 組み合わせロジックの記述

## HDL（ハードウェア記述言語）とは？

**HDL（Hardware Description Language）** は、デジタル回路をテキストで記述する言語です。

これまでのレッスンでは回路図（ゲートと配線）で設計してきましたが、HDLを使うと**コード**で回路を記述できます。

FPGAのプログラミングでは、HDLを書いて合成ツールに渡すと、FPGAの内部回路（LUTや配線）に自動変換されます。

---

## SystemVerilog とは？

このコースでは **SystemVerilog**（SV）を使います。

- Verilog HDL の拡張版
- FPGAやASICの設計で広く使われる
- `logic` 型など、使いやすい機能が追加されている

---

## module の基本構文

SystemVerilog の回路は `module` で定義します。

```systemverilog
module モジュール名 (
    input  logic 入力信号名,
    output logic 出力信号名
);
    // 回路の記述
endmodule
```

### 例：ANDゲート

```systemverilog
module and_gate (
    input  logic a,     // 入力A
    input  logic b,     // 入力B
    output logic y      // 出力Y
);
    assign y = a & b;   // ANDゲート
endmodule
```

---

## assign 文（継続的代入）

`assign` は組み合わせロジックを記述する文です。

```systemverilog
assign 出力 = 式;
```

右辺の値が変わるたびに、左辺も即座に更新されます（ゲートと同じ）。

### 主な演算子

| 演算子 | 意味 | 例 |
|--------|------|-----|
| `&`  | AND  | `assign y = a & b;` |
| `\|` | OR   | `assign y = a \| b;` |
| `~`  | NOT  | `assign y = ~a;` |
| `^`  | XOR  | `assign y = a ^ b;` |

### 多ビット信号

```systemverilog
output logic [7:0] result   // 8ビット信号（[MSB:LSB]）
assign result = 8'hFF;      // 16進数リテラル（8'h = 8ビット16進）
assign result = 8'b11001010; // 2進数リテラル
```

---

## ポートの方向

| キーワード | 意味 |
|-----------|------|
| `input`   | 入力ポート（外から受け取る）|
| `output`  | 出力ポート（外に出す）|
| `inout`   | 双方向（入出力）|

FPGAでは `logic` 型を使うのが一般的です（Verilog の `wire` / `reg` を統一した型）。

---

## コメント

```systemverilog
// 1行コメント
/* 複数行
   コメント */
```

---

## まとめ

- `module` で回路を定義する
- `input logic` / `output logic` でポートを宣言する
- `assign` で組み合わせロジックを記述する
- `&`、`|`、`~`、`^` で論理演算を書く

**下の演習エリアで実際にコードを書いてみましょう！**
