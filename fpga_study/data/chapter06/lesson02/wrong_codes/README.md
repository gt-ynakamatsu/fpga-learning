# Ch06 Lesson02 よくある誤りコード — 2:1 MUX

## spec.yaml の確認内容

- 全8通りの入力組み合わせ（at:3 で同サイクル set & check）
- latch_detection: sel を変更後に保持が起きるか確認
- mid_cycle_sel_change: エッジ後（offset_ns:2）に sel=0 を設定し、offset_ns:3 で y=0 を確認

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | 誤りの内容 | expected | 検出するケース |
|---------|-----------|---------|--------------|
| sel_xor_a.sv | `y = sel ^ a` | **FAIL** | sel1_a0_b0, sel1_a1_b1 |
| a_or_sel_and_b.sv | `y = a\|(sel&b)` | **FAIL** | sel1_a1_b0 |
| latch.sv | else なし → ラッチ | **FAIL** | latch_detection |
| mux_reg1.sv | 1段 FF 出力（出力 FF 経由） | **FAIL** | mid_cycle_sel_change（offset_ns） |

## 機械可読な期待値

`manifest.yaml` に `expected: FAIL | PASS_KNOWN_LIMITATION` と理由を記載。
統合テスト (`test_hdl_integration.py`) は manifest.yaml を読み込んで動作します。
