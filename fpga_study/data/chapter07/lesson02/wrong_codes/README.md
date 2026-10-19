# Ch07 Lesson02 よくある誤りコード — counter4

## spec.yaml の確認内容

- 0→15 のカウントアップ（counts_up: at 4-7）
- 15→0 のオーバーフロー（overflow_15_to_0: at 18-20）
- 動作中の同期リセット（sync_reset_during_count: at 8-9）
- 初期リセット（reset_to_zero: at 2）

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | 誤りの内容 | expected | 検出するケース |
|---------|-----------|---------|--------------|
| saturate_at_15.sv | 15 で飽和して 0 に戻らない | **FAIL** | overflow_15_to_0 |
| count_0_to_9.sv | 0〜9 の 10 進カウンタ | **FAIL** | overflow_15_to_0 |
| no_reset.sv | rst チェックなし | **FAIL** | counts_up |
| async_reset.sv | 非同期リセット | **PASS_KNOWN_LIMITATION** | 下記参照 |

## ⚠️ 整数サイクル制約（PASS_KNOWN_LIMITATION）

`async_reset.sv` は deltasim の整数サイクル検査では現在 PASS します。

**理由**: `always_ff @(posedge clk or posedge rst)` は非同期リセットですが、
rst の変化がクロックエッジと同時のため、同期リセットと区別できません。

**対応予定**: deltasim がサブサイクル刺激に対応した時点で FAIL に変更します。

## 機械可読な期待値

`manifest.yaml` に `expected: FAIL | PASS_KNOWN_LIMITATION` と理由を記載しています。
統合テスト (`test_hdl_integration.py`) は manifest.yaml を読み込んで動作します。
