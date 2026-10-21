// よくある誤り: 0〜9 の 10 進カウンタ（4 ビットの 0〜15 ではない）
// → overflow_15_to_0 ケース（at:18 で count=15 期待）で FAIL する
module counter4(
    input  logic       clk,
    input  logic       rst,
    output logic [3:0] count
);
    always_ff @(posedge clk) begin
        if (rst) count <= 4'b0;
        else if (count == 4'd9) count <= 4'b0;  // 誤り: 10 で折り返し
        else count <= count + 4'b1;
    end
endmodule
