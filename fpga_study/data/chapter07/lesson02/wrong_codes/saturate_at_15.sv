// よくある誤り: 15 で飽和するカウンタ（0に戻らない）
// → overflow_15_to_0 ケース（at:19 で count=0 期待）で FAIL する
module counter4(
    input  logic       clk,
    input  logic       rst,
    output logic [3:0] count
);
    always_ff @(posedge clk) begin
        if (rst) count <= 4'b0;
        else if (count != 4'hF)
            count <= count + 4'b1;
        // 誤り: count == 15 のとき count のまま（0に戻らない）
    end
endmodule
