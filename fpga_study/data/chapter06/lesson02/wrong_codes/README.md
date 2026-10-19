# Ch06 Lesson02 よくある誤りコード — 2:1 MUX

## spec.yaml の確認内容

全 8 通りの入力組み合わせ（sel ∈ {0,1}、a ∈ {0,1}、b ∈ {0,1}）をすべてチェック。

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | 誤りの内容 | expected | 検出するケース |
|---------|-----------|---------|--------------|
| sel_xor_a.sv | `y = sel ^ a`（XOR） | **FAIL** | sel1_a0_b0, sel1_a1_b1 |
| a_or_sel_and_b.sv | `y = a \| (sel & b)` | **FAIL** | sel1_a1_b0 |

いずれも整数サイクル境界での検査で FAIL が確認済みです。

## 機械可読な期待値

`manifest.yaml` に `expected: FAIL | PASS_KNOWN_LIMITATION` と理由を記載しています。
統合テスト (`test_hdl_integration.py`) は manifest.yaml を読み込んで動作します。
