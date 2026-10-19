# always_ff — フリップフロップと同期リセット

## always_ff とは？

`always_ff` は順序回路（フリップフロップ）を記述するブロックです。

```systemverilog
always_ff @(posedge clk) begin
    // クロックの立ち上がりに同期して実行される
end
```

`@(posedge clk)` は「clk の立ち上がりエッジのとき」という意味です。

---

> ## ⚠️ 必ず守るルール
>
> **順序回路（記憶を持つ回路）は、必ず `always_ff @(posedge clk)` の中に書いてください。**
>
> リセットは、そのブロックの中で `if (rst)` を使って処理します（同期リセット）。
>
> ```systemverilog
> // ✅ 正しい書き方
> always_ff @(posedge clk) begin
>     if (rst) q <= 1'b0;   // リセット時は 0 に（同期リセット）
>     else     q <= d;       // 通常動作
> end
> ```
>
> ```systemverilog
> // ❌ よくある誤り（assign は組み合わせ回路になり、FF になりません）
> assign q = rst ? 1'b0 : d;
>
> // ❌ よくある誤り（感度リストに rst を入れると非同期リセットになります）
> always_ff @(posedge clk or posedge rst) begin ... end
> ```

---

## Dフリップフロップの実装

```systemverilog
module d_ff(
    input  logic clk,  // クロック
    input  logic rst,  // 同期リセット（rst=1 でリセット）
    input  logic d,    // データ入力
    output logic q     // 出力
);
    always_ff @(posedge clk) begin
        if (rst)
            q <= 1'b0;  // リセット時は 0 に
        else
            q <= d;     // 通常はDをQに記録
    end
endmodule
```

### 非ブロッキング代入 `<=`

`always_ff` 内では `<=`（非ブロッキング代入）を使います。

- `<=`: クロックエッジ後に一斉に更新される（順序回路向け）
- `=`:  即座に代入される（`always_comb` 向け）

> **覚え方**: `always_ff` の中は必ず `<=`（矢印）、`always_comb` の中は必ず `=`（イコール）

---

## 同期リセット（この教材の標準）

この教材では **同期リセット・正論理（rst）** を使います。

```systemverilog
always_ff @(posedge clk) begin
    if (rst) q <= 1'b0;   // rst=1 でクロックに同期してリセット
    else     q <= d;
end
```

- **同期**: クロックの立ち上がりでのみリセットが効く
- **正論理**: rst=1 がリセット状態

---

## 数値リテラルの書き方

```systemverilog
1'b0    // 1ビットの 0（b = binary）
1'b1    // 1ビットの 1
4'b1010 // 4ビットの 1010₂
8'hFF   // 8ビットの 0xFF（h = hex）
```

---

## まとめ

- **順序回路は `always_ff @(posedge clk)` の中に書く**（必須ルール）
- **リセットは `if (rst) q <= 0;` でブロック内に書く**（同期リセット）
- 非ブロッキング代入 `<=` を使う
- `assign` や感度リストへの `rst` 追加は誤り

**下の演習エリアで D-FF を実装してみましょう！**
