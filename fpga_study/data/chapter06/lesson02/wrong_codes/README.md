# lesson02 よくある誤りコード

## spec.yaml の確認内容

全 8 通りの入力組み合わせ（sel ∈ {0,1}、a ∈ {0,1}、b ∈ {0,1}）をすべてチェック。

## wrong_codes

| ファイル | 誤りの内容 | 検出可否 | 検出するケース |
|---------|-----------|---------|--------------|
| sel_xor_a.sv | `y = sel ^ a`（XOR） | ✅ FAIL | sel1_a0_b0, sel1_a1_b1 |
| a_or_sel_and_b.sv | `y = a \| (sel & b)` | ✅ FAIL | sel1_a1_b0 |
