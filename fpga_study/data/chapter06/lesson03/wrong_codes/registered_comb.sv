// RULE_VIOLATION_UNDETECTABLE:
// 組み合わせ論理で rst を処理し、結果を FF で取り込む書き方。
//
// 【なぜルール違反か】
//   このコードは「always_ff @(posedge clk) の中で if (rst) を使う」という
//   コーディングルール（decisions 4）に違反している。
//
// 【なぜ検出できないか】
//   動作としては正しいコードと完全に等価であるため:
//   - 整数サイクルの spec 検査: PASS（正常）
//   - deltasim がサブサイクル刺激に対応後も: PASS のまま
//     （d_comb は always_ff エッジの直前に確定しており、観測可能な差がない）
//
// 【検出方法】
//   自動テストでは検出不可能。コードレビューで指摘する必要がある。
module d_ff(
    input  logic clk,
    input  logic rst,
    input  logic d,
    output logic q
);
    logic d_comb;
    assign d_comb = rst ? 1'b0 : d;  // ルール違反: always_ff 外で rst を処理
    always_ff @(posedge clk) q <= d_comb;
endmodule
