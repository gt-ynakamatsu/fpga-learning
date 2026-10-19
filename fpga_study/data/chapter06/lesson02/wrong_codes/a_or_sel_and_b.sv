// よくある誤り: a OR (sel AND b) を出力してしまう
// sel=1 かつ a=1 のとき、b の値に関わらず y=1 になる
// → sel1_a1_b0 ケース（期待: y=0）で FAIL する
module mux2to1(
    input  logic clk,
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    assign y = a | (sel & b);  // 誤り: a が 1 のとき sel に関係なく 1 になる
endmodule
