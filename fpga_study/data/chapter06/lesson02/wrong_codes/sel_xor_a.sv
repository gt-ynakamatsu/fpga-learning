// よくある誤り: sel XOR a を出力してしまう
// sel=1 かつ a=0 のとき y=1 になるが、正解は b=0 なので y=0 でなければならない
// → sel1_a0_b0 と sel1_a1_b1 ケースで FAIL する
module mux2to1(
    input  logic sel,
    input  logic a,
    input  logic b,
    output logic y
);
    assign y = sel ^ a;  // 誤り: XOR ではなく条件選択が必要
endmodule
