// PASS_KNOWN_LIMITATION: 出力をワイヤー経由で接続（機能的に正しいコードと同一）
// assign y_int = a & b; assign y = y_int; は assign y = a & b; と等価
// 整数サイクル検査では区別できない
module and_gate(
    input  logic a,
    input  logic b,
    output logic y
);
    logic y_int;
    assign y_int = a & b;
    assign y = y_int;   // 中間ワイヤーを経由するが動作は同一
endmodule
