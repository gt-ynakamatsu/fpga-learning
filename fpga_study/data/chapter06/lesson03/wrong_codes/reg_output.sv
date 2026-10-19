// PASS_KNOWN_LIMITATION:
// always_ff 内でブロッキング代入 = を使用（本来は <= を使う）。
// 旧: deltasim バグで FAIL していたが、バグ修正後は PASS する。
// 現: FF が 1 段だけなので、整数サイクル境界での観測値が正しいコードと同一。
//     §15 の offset_ns ケースでも PASS のまま。
//
// 【コーディングルール違反】
//   always_ff ブロック内では非ブロッキング代入 <= を使う（コーディング規約）。
//   ただし単一 FF の場合は動作上の差がないため自動検出できない。
//   コードレビューで指摘する必要がある。
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        if (rst) q = 1'b0;  // ルール違反: <= を使うべき
        else     q = d;      // ルール違反: <= を使うべき
    end
endmodule
