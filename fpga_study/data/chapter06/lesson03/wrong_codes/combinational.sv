// expected: FAIL
// 検出ケース: hold_between_edges（§15 offset_ns を使用）
//
// assign q = rst?0:d は組み合わせ回路（FF なし）。
// クロックエッジ間に D が変化すると、Q も即座に変化する。
// 正しい D-FF はクロックエッジまで Q を保持するが、このコードは保持しない。
//
// deltasim v0.2.0 以降（§15 offset_ns）でないと検出できない。
// 旧バージョンでは整数サイクル境界でのみ確認するため PASS していた。
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    assign q = rst ? 1'b0 : d;  // 誤り: always_ff @(posedge clk) が必要
endmodule
