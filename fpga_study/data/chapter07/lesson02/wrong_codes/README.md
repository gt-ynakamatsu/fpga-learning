# Ch07 Lesson02 よくある誤りコード — counter4

## spec.yaml の確認内容

- 0→15 のカウントアップ（counts_up: at 4-7）
- 15→0 のオーバーフロー（overflow_15_to_0: at 18-20）
- 動作中の同期リセット（sync_reset_during_count: at 8-9）
- サイクル途中の rst 変化は次エッジまで無効（sync_reset_waits_for_edge: §15 offset_ns）
- 初期リセット（reset_to_zero: at 2）

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | expected | 検出するケース |
|---------|---------|--------------|
| saturate_at_15.sv | **FAIL** | overflow_15_to_0 |
| count_0_to_9.sv | **FAIL** | overflow_15_to_0 |
| no_reset.sv | **FAIL** | counts_up |
| async_reset.sv | **FAIL** | sync_reset_waits_for_edge（§15 offset_ns） |

## §15 offset_ns について

`async_reset.sv` は §15 の `sync_reset_waits_for_edge` ケースで FAIL する。
deltasim v0.2.0 以降が必要。
