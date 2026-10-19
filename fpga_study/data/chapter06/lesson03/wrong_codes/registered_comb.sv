// PASS_KNOWN_LIMITATION: 組み合わせ論理で rst を処理し、FF で取り込む
// 動作は正しいコード（always_ff 内で if(rst)）と整数サイクル境界では同一になる
// 理由: d_comb = rst?0:d は組み合わせで計算され、その値を FF で取り込むため
//       クロックエッジ境界での観測値が同じになる
// ⚠️ deltasim の整数サイクル検査では PASS する（PASS_KNOWN_LIMITATION）
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    logic d_comb;
    assign d_comb = rst ? 1'b0 : d;  // 組み合わせで次の値を計算
    always_ff @(posedge clk) q <= d_comb;  // FF で取り込む
endmodule
