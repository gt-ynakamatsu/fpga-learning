// 第6章 lesson01 正解例 - ANDゲート (assign)
module and_gate(
    input  logic clk,
    input  logic a,
    input  logic b,
    output logic y
);
    assign y = a & b;
endmodule
