# lesson02 (chapter07) よくある誤りコード

## spec.yaml の確認内容

- 0→15 のカウントアップ (counts_up: at 4-7)
- 15→0 のオーバーフロー (overflow_15_to_0: at 18-20)
- 動作中のリセット (sync_reset_during_count: at 8-9)
- 初期リセット (reset_to_zero: at 2)

## wrong_codes

| ファイル | 誤りの内容 | 検出可否 | 検出するケース |
|---------|-----------|---------|--------------|
| saturate_at_15.sv | 15 で飽和して 0 に戻らない | ✅ FAIL | overflow_15_to_0 |
| count_0_to_9.sv | 10 進カウンタ（0〜9）| ✅ FAIL | overflow_15_to_0 |
| no_reset.sv | rst チェックなし | ✅ FAIL | counts_up |
| async_reset.sv | 非同期リセット | ⚠️ PASS（制約）| 整数サイクル境界での動作は同一 |
