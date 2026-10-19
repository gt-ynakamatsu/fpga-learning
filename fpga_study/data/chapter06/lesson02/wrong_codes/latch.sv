// よくある誤り: else ブランチがないためラッチが生成される
// sel=0 かつ a=0 のとき、前の y の値を保持する（期待値: y=0 で FAIL する）
// → latch_detection ケースで FAIL する
module mux2to1(
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    always_comb begin
        if (sel)    y = b;
        else if (a) y = a;
        // 誤り: else がない → 全条件を網羅していないためラッチが生成される
    end
endmodule
