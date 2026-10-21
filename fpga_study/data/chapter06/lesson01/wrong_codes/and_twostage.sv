// よくある誤り: 入力が 2 段の FF を経由してから AND する
// → 出力が 2 クロック遅れる
// same-cycle チェック（at:3 で set & check）で a_d2=0 のまま y=0 → FAIL する
module and_gate(
    input  logic clk,   // 間違いの根源: 組み合わせ AND に FF を追加
    input  logic a,
    input  logic b,
    output logic y
);
    logic a_d1, a_d2;
    // 2段パイプライン: a → a_d1 → a_d2
    always_ff @(posedge clk) a_d1 <= a;
    always_ff @(posedge clk) a_d2 <= a_d1;
    assign y = a_d2 & b;   // 2サイクル遅れた a を使う
endmodule
