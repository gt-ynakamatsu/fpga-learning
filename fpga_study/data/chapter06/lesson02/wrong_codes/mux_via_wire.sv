// PASS_KNOWN_LIMITATION: 中間 logic を経由（機能的に正しいコードと同一）
// 整数サイクル検査では区別できない
module mux2to1(
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    logic y_tmp;
    always_comb begin
        if (sel) y_tmp = b;
        else     y_tmp = a;
    end
    assign y = y_tmp;   // 中間ワイヤー経由（動作同一）
endmodule
