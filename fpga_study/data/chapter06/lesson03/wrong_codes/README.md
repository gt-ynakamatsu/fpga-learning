# Ch06 Lesson03 よくある誤りコード — D-FF

## spec.yaml の確認内容

- 同サイクルでの取り込み確認（same_cycle_capture: at:4 に set と check）
- D 変化後の保持（capture_d0_after_d1）
- D 変化なしでの保持（q_holds_while_d_stable）
- rst が D より優先されること（rst_overrides_d: D=1 かつ rst=1 で Q=0）
- 動作中の同期リセット（sync_reset_during_operation）
- 初期リセット（reset_clears_q）

## wrong_codes 一覧（manifest.yaml 参照）

| ファイル | 誤りの内容 | expected | 検出するケース |
|---------|-----------|---------|--------------|
| no_reset.sv | rst チェックなし | **FAIL** | rst_overrides_d, sync_reset_during_operation |
| twostage.sv | 2段パイプライン（1サイクル遅延） | **FAIL** | same_cycle_capture |
| reg_output.sv | always_ff 内でブロッキング代入 | **FAIL** | 複数ケース（deltasim 挙動） |
| combinational.sv | assign q = rst?0:d（FF なし） | **PASS_KNOWN_LIMITATION** | 下記参照 |
| async_reset.sv | 非同期リセット | **PASS_KNOWN_LIMITATION** | 下記参照 |
| registered_comb.sv | 組み合わせで rst 処理→FF で取り込み | **PASS_KNOWN_LIMITATION** | 下記参照 |

## ⚠️ 整数サイクル制約（PASS_KNOWN_LIMITATION）

`combinational.sv`、`async_reset.sv`、`registered_comb.sv` は現在 PASS します。

**理由**: deltasim の spec.yaml はクロックエッジ境界（整数サイクル）でのみ入力変化を指定できます。
これらのコードはクロックエッジ以外のタイミングで正常コードと動作が異なりますが、
整数サイクル検査では同一の観測値になります。

**対応予定**: deltasim がサブサイクル刺激に対応した時点で、
manifest.yaml の expected を `FAIL` に変更し、統合テストを更新してください。
統合テストは PASS_KNOWN_LIMITATION エントリが PASS であることをアサートするため、
deltasim の対応後にアサートが壊れます（その時が更新の合図です）。

## 機械可読な期待値

`manifest.yaml` に `expected: FAIL | PASS_KNOWN_LIMITATION` と理由を記載しています。
統合テスト (`test_hdl_integration.py`) は manifest.yaml を読み込んで動作します。
