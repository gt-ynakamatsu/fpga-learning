// よくある誤り: D→Q1（1段目FF）→Q（2段目FF）の2段パイプライン
// クロックが1回余分にかかるため、same_cycle_capture ケースで FAIL する
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    logic q1;
    always_ff @(posedge clk) begin
        if (rst) begin q1 <= 1'b0; q <= 1'b0; end
        else     begin q1 <= d;    q <= q1;    end
    end
endmodule
