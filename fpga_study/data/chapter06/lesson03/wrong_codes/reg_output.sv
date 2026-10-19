// FAIL_DUE_TO_DELTASIM_BUG:
// always_ff 内でブロッキング代入 = を使用（本来は <= を使う）。
// この実装の意図は正しい DFF と同等だが、deltasim バグ（クロック付きブロック内の
// blocking assign が q を正しく更新しない）により現在 FAIL する。
//
// 【deltasim バグ報告中】仕様考案係が deltasim 開発チームに報告済み。
// バグ修正後は PASS になる可能性があるため、その時点で manifest.yaml を更新すること。
//
// 参考: § 正しいスタイルは always_ff 内では <= を使う（コーディングルール）
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        if (rst) q = 1'b0;  // バグ: <= を使うべきだが、= を使用
        else     q = d;      // バグ: 同上
    end
endmodule
