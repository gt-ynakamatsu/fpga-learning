// 第6章 lesson03 正解例 - D-FF (always_ff, 同期リセット正論理)
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        if (rst) q <= 1'b0;
        else     q <= d;
    end
endmodule
