// 第6章 lesson02 正解例 - 2:1 MUX (always_comb)
module mux2to1(
    input  logic clk,
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    always_comb begin
        if (sel)
            y = b;
        else
            y = a;
    end
endmodule
