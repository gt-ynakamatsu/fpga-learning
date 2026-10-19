// PASS_KNOWN_LIMITATION: 出力を1段 FF に通す（正しくは組み合わせ assign）
// 整数サイクル検査（offset_ns=0）では区別できない
// 理由: D=a&b を FF で取り込む場合、at:N の edge では a&b が既に確定しているため
//       at:N check でも同じ値になる
// §15 の offset_ns を使えば「エッジ前の中間値」で区別可能だが、
// §15 spec に追加されていない（コーディングルール違反として扱う）
module and_gate(
    input  logic clk,  // 出力 FF に必要（正しい AND には不要）
    input  logic a,
    input  logic b,
    output logic y
);
    always_ff @(posedge clk) y <= a & b;  // 誤り: 組み合わせ AND を FF 越しに出力
endmodule
