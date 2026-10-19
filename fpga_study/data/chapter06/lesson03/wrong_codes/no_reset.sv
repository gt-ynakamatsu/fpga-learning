// よくある誤り: リセット処理がない
// rst=1 でも q は d を通常通り取り込む
// → sync_reset_during_operation ケースで FAIL する
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        q <= d;  // 誤り: rst チェックがない
    end
endmodule
