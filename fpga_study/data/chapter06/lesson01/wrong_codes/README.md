# Ch06 Lesson01 よくある誤りコード — AND gate

## spec.yaml の確認内容

- 全4通りの入力組み合わせ（at:3 で同サイクル set & check）
- mid_cycle_b_zero: エッジ後（offset_ns:2）に b=0 を設定し、offset_ns:3 で y=0 を確認

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | 誤りの内容 | expected | 検出するケース |
|---------|-----------|---------|--------------|
| and_twostage.sv | 2段 FF パイプライン | **FAIL** | 同サイクルチェック（at:3） |
| and_reg1.sv | 1段 FF 出力（出力 FF 経由） | **FAIL** | mid_cycle_b_zero（offset_ns） |

## 機械可読な期待値

`manifest.yaml` に `expected: FAIL | PASS_KNOWN_LIMITATION` と理由を記載。
統合テスト (`test_hdl_integration.py`) は manifest.yaml を読み込んで動作します。
