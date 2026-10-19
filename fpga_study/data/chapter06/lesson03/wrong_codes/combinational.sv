// よくある誤り: フリップフロップではなく組み合わせ回路（assign）で記述
// クロックに同期せず、d や rst が変わると q も即座に変わる
// ⚠️ deltasim の整数サイクル検査では PASS してしまう（制約あり）
// 理由: クロックエッジでのみ入力を変えている場合、DFF と同じ観測値になる
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    assign q = rst ? 1'b0 : d;  // 誤り: always_ff @(posedge clk) が必要
endmodule
