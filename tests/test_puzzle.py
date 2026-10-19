"""回路パズル評価ロジックのテスト"""

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
        # AND ゲートで XOR を解こうとしても失敗する
        gates = [{"id": "gate_1", "type": "AND", "x": 300, "y": 200}]
        conns = [
            {"from_id": "input_A", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_0"},
            {"from_id": "input_B", "from_port": "output_0", "to_id": "gate_1", "to_port": "input_1"},
            {"from_id": "gate_1", "from_port": "output_0", "to_id": "output_Y", "to_port": "input_0"},
        ]
        result = evaluate_circuit(PUZZLE_XOR, conns, gates)
        assert result["passed"] is False
