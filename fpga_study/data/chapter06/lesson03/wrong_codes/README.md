# Ch06 Lesson03 よくある誤りコード — D-FF

## spec.yaml の確認内容

- 同サイクル取り込み（same_cycle_capture: at:4）
- D 変化後の保持（capture_d0_after_d1）
- 安定時の保持（q_holds_while_d_stable）
- rst が D より優先（rst_overrides_d）
- 動作中の同期リセット（sync_reset_during_operation）
- サイクル途中の D 変化・Q 保持（hold_between_edges: §15 offset_ns）
- サイクル途中の rst 変化は次エッジまで無効（sync_reset_waits_for_edge: §15 offset_ns）

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | expected | 検出するケース |
|---------|---------|--------------|
| no_reset.sv | **FAIL** | rst_overrides_d, sync_reset_during_operation |
| twostage.sv | **FAIL** | same_cycle_capture (at:4) |
| reg_output.sv | **PASS_KNOWN_LIMITATION** | deltasim バグ修正後PASS。ブロッキング=はコーディングルール違反 |
| combinational.sv | **FAIL** | hold_between_edges（§15 offset_ns） |
| async_reset.sv | **FAIL** | sync_reset_waits_for_edge（§15 offset_ns） |
| registered_comb.sv | **PASS_KNOWN_LIMITATION** | 機能的に正しいコードと等価。コーディングルール違反 |

## 整数サイクル vs §15 offset_ns

- `combinational.sv` と `async_reset.sv` は §15 offset_ns ケースで FAIL する
- `registered_comb.sv` は §15 offset_ns 後もPASS（動作が正しいコードと等価）
- deltasim v0.2.0 以降が必要（§15 サポート）
