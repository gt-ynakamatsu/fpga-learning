// PASS_KNOWN_LIMITATION: 出力を1段 FF に通す（正しくは組み合わせ always_comb）
// 整数サイクル検査では区別できない（コーディングルール違反として扱う）
module mux2to1(
    input  logic clk,  // 出力 FF に必要（正しい MUX には不要）
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    always_ff @(posedge clk) begin
        if (sel) y <= b;
        else     y <= a;
    end
endmodule
