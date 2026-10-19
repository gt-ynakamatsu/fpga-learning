# lesson03 よくある誤りコード

## spec.yaml の確認内容

- クロックエッジで D を捕捉すること (capture_d1, capture_d0_after_d1)
- D が変化しても Q が保持されること (q_holds_while_d_stable)
- 動作中のリセット (sync_reset_during_operation)
- 初期リセット (reset_clears_q)

## wrong_codes

| ファイル | 誤りの内容 | 検出可否 | 理由 |
|---------|-----------|---------|------|
| no_reset.sv | `q <= d`（rst チェックなし） | ✅ FAIL | sync_reset_during_operation で検出 |
| combinational.sv | `assign q = rst?0:d`（FF なし） | ⚠️ PASS（制約）| deltasim の整数サイクル検査では DFF と同一に見える |
| async_reset.sv | 感度リストに rst を追加（非同期リセット） | ⚠️ PASS（制約）| rst の変化がクロックエッジと同時のため区別不可 |

## 整数サイクル制約について

deltasim の `spec.yaml` では入力変化はクロックサイクル境界（整数）でのみ指定できます。
`combinational.sv` と `async_reset.sv` は、クロックエッジ以外のタイミングでの動作が
正常コードと異なりますが、整数サイクル検査では同一の出力を生成します。
これは deltasim の spec フォーマットの制約であり、sub-cycle タイミング検査が
サポートされた場合に追加確認が可能になります。
