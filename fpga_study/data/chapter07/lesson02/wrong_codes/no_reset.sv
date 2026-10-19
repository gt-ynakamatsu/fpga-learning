// よくある誤り: リセット処理がない
// rst=1 でも count は増加し続ける
// → counts_up ケース（初期 count=1 期待）で FAIL する
module counter4(
    input  logic       clk,
    input  logic       rst,
    output logic [3:0] count
);
    always_ff @(posedge clk) begin
        count <= count + 4'b1;  // 誤り: rst チェックなし
    end
endmodule
