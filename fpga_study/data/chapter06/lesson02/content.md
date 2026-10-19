# always_comb — 条件分岐と MUX

## always_comb とは？

`always_comb` は組み合わせロジックを手続き的に記述するブロックです。

```systemverilog
always_comb begin
    // ここに組み合わせロジックを書く
end
```

`assign` は1行で書けるシンプルな式向き。`always_comb` は **if/else** や **case** など複雑な条件分岐に向いています。

---

## if/else 文

```systemverilog
always_comb begin
    if (条件) begin
        y = 値1;
    end else begin
        y = 値2;
    end
end
```

### 例：2:1 MUX

```systemverilog
module mux2to1(
    input  logic clk,
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    always_comb begin
        if (sel)
            y = b;   // sel=1 なら b を選ぶ
        else
            y = a;   // sel=0 なら a を選ぶ
    end
endmodule
```

---

## case 文

複数の条件をきれいに書くなら `case` が便利です。

```systemverilog
always_comb begin
    case (sel)
        2'b00: y = a;
        2'b01: y = b;
        2'b10: y = c;
        2'b11: y = d;
        default: y = a;  // それ以外（念のため）
    endcase
end
```

---

## 重要：always_comb では全パターンを網羅する

`always_comb` 内の変数は、**すべての条件で値を割り当てる**必要があります。
そうしないと「ラッチ（Latch）」が生成される可能性があります（意図しない記憶素子）。

- if に対して else を必ず書く
- case に default を必ず書く

---

## まとめ

- `always_comb` は組み合わせロジックを if/else や case で書ける
- 全パターンで値を割り当てないとラッチが生成される
- 2:1 MUX: sel=0 なら a、sel=1 なら b を出力

**下の演習エリアで 2:1 MUX を実装してみましょう！**
