// expected: FAIL
// 検出ケース: sync_reset_waits_for_edge（§15 offset_ns を使用）
//
// always_ff @(posedge clk or posedge rst) は非同期リセット。
// サイクルの途中で rst=1 になると Q がすぐに 0 になる。
// 同期リセットではクロックエッジまで Q が変化しないはずだが、
// このコードは即座にリセットしてしまう。
//
// deltasim v0.2.0 以降（§15 offset_ns）でないと検出できない。
// 旧バージョンでは整数サイクル境界でのみ確認するため PASS していた。
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk or posedge rst) begin  // 誤り: 感度リストに rst を入れてはいけない
        if (rst) q <= 1'b0;
        else     q <= d;
    end
endmodule
