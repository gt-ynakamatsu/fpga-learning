"""always_ff 内ブロッキング代入の lint テスト"""

from __future__ import annotations

from fpga_study.content.lint import lint_hdl


class TestAlwaysFfLint:
    def test_no_hints_for_correct_code(self):
        code = """
module d_ff(input logic clk, rst, d, output logic q);
    always_ff @(posedge clk) begin
        if (rst) q <= 1'b0;
        else     q <= d;
    end
endmodule
"""
        hints = lint_hdl(code)
        assert hints == []

    def test_hint_for_blocking_assign_in_ff(self):
        code = """
module d_ff(input logic clk, rst, d, output logic q);
    always_ff @(posedge clk) begin
        if (rst) q = 1'b0;
        else     q = d;
    end
endmodule
"""
        hints = lint_hdl(code)
        assert len(hints) == 1
        assert "<=" in hints[0]
        assert "ブロッキング" in hints[0] or "=" in hints[0]

    def test_no_hint_for_assign_outside_ff(self):
        """always_ff の外の assign は対象外"""
        code = """
module and_gate(input logic a, b, output logic y);
    assign y = a & b;
endmodule
"""
        hints = lint_hdl(code)
        assert hints == []

    def test_no_hint_for_comb(self):
        """always_comb 内の = は正常"""
        code = """
module mux(input logic sel, a, b, output logic y);
    always_comb begin
        if (sel) y = b;
        else     y = a;
    end
endmodule
"""
        hints = lint_hdl(code)
        assert hints == []

    def test_no_hint_for_comparison(self):
        """== などの比較演算子は誤検知しない"""
        code = """
module counter(input logic clk, rst, output logic [3:0] count);
    always_ff @(posedge clk) begin
        if (rst) count <= 4'b0;
        else if (count == 4'hF) count <= 4'b0;
        else count <= count + 1;
    end
endmodule
"""
        hints = lint_hdl(code)
        assert hints == []

    def test_hint_message_is_beginner_friendly(self):
        """ヒントメッセージが初心者向けであること（begin...end が必要）"""
        code = """
module d_ff(input logic clk, input logic d, output logic q);
    always_ff @(posedge clk) begin
        q = d;
    end
endmodule
"""
        hints = lint_hdl(code)
        assert len(hints) >= 1
        assert "<=" in hints[0]
        # スタックトレースなどがないこと
        assert "Traceback" not in hints[0]
        assert "Error" not in hints[0]
