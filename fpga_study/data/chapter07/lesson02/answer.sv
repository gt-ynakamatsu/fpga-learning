// 第7章 lesson02 正解例 - 4ビットカウンタ (always_ff, 同期リセット正論理)
module counter4(
    input  logic       clk,
    input  logic       rst,
    output logic [3:0] count
);
    always_ff @(posedge clk) begin
        if (rst)
            count <= 4'b0;
        else
            count <= count + 4'b1;
    end
endmodule
