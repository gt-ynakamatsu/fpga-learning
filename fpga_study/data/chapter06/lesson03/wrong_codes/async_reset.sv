// よくある誤り: 非同期リセット（always_ff の感度リストに rst を追加）
// 同期リセット (decisions 4) では rst を感度リストに入れてはいけない
// ⚠️ deltasim の整数サイクル検査では PASS してしまう（制約あり）
// 理由: rst の変化が常にクロックエッジと同時のため、外部からは区別できない
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk or posedge rst) begin  // 誤り: rst を感度リストに入れない
        if (rst) q <= 1'b0;
        else     q <= d;
    end
endmodule
