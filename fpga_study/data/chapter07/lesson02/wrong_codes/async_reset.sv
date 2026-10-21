// よくある誤り: 非同期リセット（decisions 4 違反）
// ⚠️ deltasim の整数サイクル検査では PASS してしまう（制約あり）
// 理由: rst の変化がクロックエッジと同時のため、外部から動作が区別できない
module counter4(
    input  logic       clk,
    input  logic       rst,
    output logic [3:0] count
);
    always_ff @(posedge clk or posedge rst) begin  // 誤り
        if (rst) count <= 4'b0;
        else count <= count + 4'b1;
    end
endmodule
