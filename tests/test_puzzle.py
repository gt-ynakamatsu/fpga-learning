"""回路パズル評価ロジックのテスト（組み合わせ回路 + 順序回路）"""

from __future__ import annotations

import pytest

from fpga_study.content.loader import evaluate_circuit


PUZZLE_AND = {
    "inputs": [{"name": "A"}, {"name": "B"}],
    "outputs": [{"name": "Y"}],
    "available_gates": [{"type": "AND", "count": 1}],
    "target_truth_table": [
        {"inputs": {"A": 0, "B": 0}, "outputs": {"Y": 0}},
        {"inputs": {"A": 0, "B": 1}, "outputs": {"Y": 0}},
        {"inputs": {"A": 1, "B": 0}, "outputs": {"Y": 0}},
        {"inputs": {"A": 1, "B": 1}, "outputs": {"Y": 1}},
    ],
}

PUZZLE_OR = {
    "inputs": [{"name": "A"}, {"name": "B"}],
    "outputs": [{"name": "Y"}],
    "available_gates": [{"type": "OR", "count": 1}],
    "target_truth_table": [
        {"inputs": {"A": 0, "B": 0}, "outputs": {"Y": 0}},
        {"inputs": {"A": 0, "B": 1}, "outputs": {"Y": 1}},
        {"inputs": {"A": 1, "B": 0}, "outputs": {"Y": 1}},
        {"inputs": {"A": 1, "B": 1}, "outputs": {"Y": 1}},
    ],
}

PUZZLE_NOT = {
    "inputs": [{"name": "A"}],
    "outputs": [{"name": "Y"}],
    "available_gates": [{"type": "NOT", "count": 1}],
    "target_truth_table": [
        {"inputs": {"A": 0}, "outputs": {"Y": 1}},
        {"inputs": {"A": 1}, "outputs": {"Y": 0}},
    ],
}

PUZZLE_XOR = {
    "inputs": [{"name": "A"}, {"name": "B"}],
    "outputs": [{"name": "Y"}],
    "available_gates": [{"type": "XOR", "count": 1}],
    "target_truth_table": [
        {"inputs": {"A": 0, "B": 0}, "outputs": {"Y": 0}},
        {"inputs": {"A": 0, "B": 1}, "outputs": {"Y": 1}},
        {"inputs": {"A": 1, "B": 0}, "outputs": {"Y": 1}},
        {"inputs": {"A": 1, "B": 1}, "outputs": {"Y": 0}},
    ],
}


def make_and_circuit():
    """AND ゲートを正しく配線した場合の接続情報"""
    gate_placements = [{"id": "gate_1", "type": "AND", "x": 300, "y": 200}]
    connections = [
        {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
        {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
        {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
    ]
    return connections, gate_placements


def make_or_circuit():
    gate_placements = [{"id": "gate_1", "type": "OR", "x": 300, "y": 200}]
    connections = [
        {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
        {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
        {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
    ]
    return connections, gate_placements


def make_not_circuit():
    gate_placements = [{"id": "gate_1", "type": "NOT", "x": 300, "y": 200}]
    connections = [
        {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
        {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
    ]
    return connections, gate_placements


def make_xor_circuit():
    gate_placements = [{"id": "gate_1", "type": "XOR", "x": 300, "y": 200}]
    connections = [
        {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
        {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
        {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
    ]
    return connections, gate_placements


class TestAndPuzzle:
    def test_correct_and_circuit_passes(self):
        conns, gates = make_and_circuit()
        result = evaluate_circuit(PUZZLE_AND, conns, gates)
        assert result["passed"] is True
        assert result["failed_cases"] == []
        assert "合格" in result["message"]

    def test_wrong_gate_type_fails(self):
        gates = [{"id": "gate_1", "type": "OR", "x": 300, "y": 200}]
        conns = [
            {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
            {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
        ]
        result = evaluate_circuit(PUZZLE_AND, conns, gates)
        assert result["passed"] is False
        assert len(result["failed_cases"]) > 0

    def test_disconnected_circuit_fails(self):
        result = evaluate_circuit(PUZZLE_AND, [], [])
        assert result["passed"] is False


class TestOrPuzzle:
    def test_correct_or_circuit_passes(self):
        conns, gates = make_or_circuit()
        result = evaluate_circuit(PUZZLE_OR, conns, gates)
        assert result["passed"] is True


class TestNotPuzzle:
    def test_correct_not_circuit_passes(self):
        conns, gates = make_not_circuit()
        result = evaluate_circuit(PUZZLE_NOT, conns, gates)
        assert result["passed"] is True

    def test_failed_case_details(self):
        # 何も接続しない場合（出力は常に0）
        result = evaluate_circuit(PUZZLE_NOT, [], [])
        assert result["passed"] is False
        # 入力A=0のとき Y=1が期待されるが 0が返る → 失敗ケースに含まれるはず
        fail_inputs = [fc["inputs"] for fc in result["failed_cases"]]
        assert {"A": 0} in fail_inputs


class TestXorPuzzle:
    def test_correct_xor_circuit_passes(self):
        conns, gates = make_xor_circuit()
        result = evaluate_circuit(PUZZLE_XOR, conns, gates)
        assert result["passed"] is True

    def test_and_gate_fails_xor_puzzle(self):
        gates = [{"id": "gate_1", "type": "AND", "x": 300, "y": 200}]
        conns = [
            {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
            {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
        ]
        result = evaluate_circuit(PUZZLE_XOR, conns, gates)
        assert result["passed"] is False


# ── 半加算器パズル（Chapter3 lesson3） ──────────────────────────────────

PUZZLE_HALF_ADDER = {
    "inputs": [{"name": "A"}, {"name": "B"}],
    "outputs": [{"name": "SUM"}, {"name": "CARRY"}],
    "available_gates": [{"type": "XOR", "count": 1}, {"type": "AND", "count": 1}],
    "target_truth_table": [
        {"inputs": {"A": 0, "B": 0}, "outputs": {"SUM": 0, "CARRY": 0}},
        {"inputs": {"A": 0, "B": 1}, "outputs": {"SUM": 1, "CARRY": 0}},
        {"inputs": {"A": 1, "B": 0}, "outputs": {"SUM": 1, "CARRY": 0}},
        {"inputs": {"A": 1, "B": 1}, "outputs": {"SUM": 0, "CARRY": 1}},
    ],
}


class TestHalfAdderPuzzle:
    def _make_half_adder(self):
        gates = [
            {"id": "xor_1", "type": "XOR", "x": 300, "y": 150},
            {"id": "and_1", "type": "AND", "x": 300, "y": 280},
        ]
        conns = [
            {"from_id": "input_A", "from_port": "output_0", "to_id": "xor_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "xor_1", "to_port": "input_1"},
            {"from_id": "input_A", "from_port": "output_0", "to_id": "and_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "and_1", "to_port": "input_1"},
            {"from_id": "xor_1", "from_port": "output_0", "to_id": "output_SUM", "to_port": "input_0"},
            {"from_id": "and_1", "from_port": "output_0", "to_id": "output_CARRY", "to_port": "input_0"},
        ]
        return conns, gates

    def test_correct_half_adder_passes(self):
        conns, gates = self._make_half_adder()
        result = evaluate_circuit(PUZZLE_HALF_ADDER, conns, gates)
        assert result["passed"] is True

    def test_swapped_gates_fails(self):
        # XOR と AND を入れ替えると失敗する
        gates = [
            {"id": "and_1", "type": "AND", "x": 300, "y": 150},
            {"id": "xor_1", "type": "XOR", "x": 300, "y": 280},
        ]
        conns = [
            {"from_id": "input_A", "from_port": "output_0", "to_id": "and_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "and_1", "to_port": "input_1"},
            {"from_id": "input_A", "from_port": "output_0", "to_id": "xor_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "xor_1", "to_port": "input_1"},
            {"from_id": "and_1", "from_port": "output_0", "to_id": "output_SUM", "to_port": "input_0"},
            {"from_id": "xor_1", "from_port": "output_0", "to_id": "output_CARRY", "to_port": "input_0"},
        ]
        result = evaluate_circuit(PUZZLE_HALF_ADDER, conns, gates)
        assert result["passed"] is False


# ── 順序回路（DFF）パズル（Chapter4 lesson3） ──────────────────────────

PUZZLE_DFF = {
    "type": "sequential",
    "inputs": [{"name": "D"}],
    "outputs": [{"name": "Q"}],
    "available_gates": [{"type": "DFF", "count": 1}],
    "target_truth_table": [
        {"clock": 0, "inputs": {"D": 1}, "outputs": {"Q": 0}},
        {"clock": 1, "inputs": {"D": 1}, "outputs": {"Q": 1}},
        {"clock": 2, "inputs": {"D": 0}, "outputs": {"Q": 1}},
        {"clock": 3, "inputs": {"D": 0}, "outputs": {"Q": 0}},
    ],
}


def make_dff_circuit():
    gates = [{"id": "dff_1", "type": "DFF", "x": 300, "y": 200}]
    conns = [
        {"from_id": "input_D", "from_port": "output_0", "to_id": "dff_1", "to_port": "input_0"},
        {"from_id": "dff_1", "from_port": "output_0", "to_id": "output_Q", "to_port": "input_0"},
    ]
    return conns, gates


class TestSequentialDffPuzzle:
    def test_correct_dff_circuit_passes(self):
        conns, gates = make_dff_circuit()
        result = evaluate_circuit(PUZZLE_DFF, conns, gates)
        assert result["passed"] is True

    def test_initial_state_is_zero(self):
        """初期状態（clock=0）では Q=0"""
        conns, gates = make_dff_circuit()
        result = evaluate_circuit(PUZZLE_DFF, conns, gates)
        # 全サイクル合格のこと
        assert result["passed"] is True
        assert result["failed_cases"] == []

    def test_disconnected_dff_fails(self):
        """DFFを配線しないと出力は常に0で失敗する"""
        result = evaluate_circuit(PUZZLE_DFF, [], [])
        assert result["passed"] is False

    def test_failed_cases_contain_clock(self):
        """失敗ケースにはclockフィールドが含まれる"""
        result = evaluate_circuit(PUZZLE_DFF, [], [])
        assert result["passed"] is False
        for fc in result["failed_cases"]:
            assert "clock" in fc

    def test_message_mentions_sequential(self):
        """順序回路の合格メッセージにはクロックの言及がある"""
        conns, gates = make_dff_circuit()
        result = evaluate_circuit(PUZZLE_DFF, conns, gates)
        assert "クロック" in result["message"] or "サイクル" in result["message"]
