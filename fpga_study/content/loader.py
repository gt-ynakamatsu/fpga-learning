"""教材コンテンツ（Markdown + YAML）の読み込みモジュール"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any, Optional

import markdown
import yaml

from fpga_study.content.validator import (
    ValidationError,
    validate_chapter_meta,
    validate_puzzle,
    validate_quiz,
)


def _data_root() -> Path:
    """教材データディレクトリのパスを返す"""
    try:
        ref = importlib.resources.files("fpga_study") / "data"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent.parent / "data"


def load_chapters(data_root: Optional[Path] = None) -> list[dict]:
    """
    全章のメタデータを order 順で返す。
    status フィールドが存在する場合はそのまま含める（draft 等）。
    """
    root = data_root or _data_root()
    chapters: list[dict] = []
    for chapter_dir in sorted(root.iterdir()):
        if not chapter_dir.is_dir():
            continue
        meta_path = chapter_dir / "meta.yaml"
        if not meta_path.exists():
            continue
        try:
            meta = _load_yaml(meta_path)
            validate_chapter_meta(meta)
            meta["_dir"] = str(chapter_dir)
            chapters.append(meta)
        except (ValidationError, Exception):
            pass
    chapters.sort(key=lambda c: c.get("order", 999))
    return chapters


def load_chapter(chapter_id: str, data_root: Optional[Path] = None) -> Optional[dict]:
    """特定の章メタデータを返す"""
    for ch in load_chapters(data_root):
        if ch["id"] == chapter_id:
            return ch
    return None


def load_lessons(chapter_id: str, data_root: Optional[Path] = None) -> list[dict]:
    """
    章に含まれるレッスンのメタデータ一覧を返す。
    meta.yaml の lessons リストの順序に従う。
    """
    root = data_root or _data_root()
    chapter_dir = root / chapter_id
    meta_path = chapter_dir / "meta.yaml"
    if not meta_path.exists():
        return []
    chapter_meta = _load_yaml(meta_path)
    lesson_ids: list[str] = chapter_meta.get("lessons", [])

    lessons: list[dict] = []
    for lesson_id in lesson_ids:
        lesson_dir = chapter_dir / lesson_id
        meta = _load_lesson_meta(lesson_dir, chapter_id, lesson_id)
        if meta:
            lessons.append(meta)
    return lessons


def load_lesson(
    chapter_id: str, lesson_id: str, data_root: Optional[Path] = None
) -> Optional[dict]:
    """レッスンの全情報（メタ + HTML化した本文 + クイズ + パズル定義）を返す"""
    root = data_root or _data_root()
    lesson_dir = root / chapter_id / lesson_id

    if not lesson_dir.exists():
        return None

    meta = _load_lesson_meta(lesson_dir, chapter_id, lesson_id)
    if not meta:
        return None

    content_md = lesson_dir / "content.md"
    if content_md.exists():
        md_text = content_md.read_text(encoding="utf-8")
        meta["content_html"] = _render_markdown(md_text)
    else:
        meta["content_html"] = ""

    quiz_path = lesson_dir / "quiz.yaml"
    if quiz_path.exists():
        try:
            quiz_data = _load_yaml(quiz_path)
            validate_quiz(quiz_data)
            meta["quiz"] = quiz_data
        except ValidationError:
            meta["quiz"] = None
    else:
        meta["quiz"] = None

    puzzle_path = lesson_dir / "puzzle.yaml"
    if puzzle_path.exists():
        try:
            puzzle_data = _load_yaml(puzzle_path)
            validate_puzzle(puzzle_data)
            meta["puzzle"] = puzzle_data
        except ValidationError:
            meta["puzzle"] = None
    else:
        meta["puzzle"] = None

    return meta


def check_quiz_answer(
    chapter_id: str,
    lesson_id: str,
    question_id: str,
    answer_index: int,
    data_root: Optional[Path] = None,
) -> dict:
    """
    クイズの回答を採点して結果を返す。
    戻り値: {correct: bool, correct_index: int, explanation: str}
    """
    root = data_root or _data_root()
    quiz_path = root / chapter_id / lesson_id / "quiz.yaml"
    if not quiz_path.exists():
        raise FileNotFoundError(f"クイズファイルが見つかりません: {quiz_path}")

    quiz_data = _load_yaml(quiz_path)
    questions = quiz_data.get("questions", [])
    question = next((q for q in questions if q["id"] == question_id), None)
    if question is None:
        raise ValueError(f"問題IDが見つかりません: {question_id}")

    correct_index: int = question["answer"]
    correct = answer_index == correct_index
    return {
        "correct": correct,
        "correct_index": correct_index,
        "explanation": question.get("explanation", ""),
    }


def check_puzzle_solution(
    chapter_id: str,
    lesson_id: str,
    connections: list[dict],
    gate_placements: list[dict],
    data_root: Optional[Path] = None,
) -> dict:
    """
    回路パズルの解答を検証する。
    真理値表の全パターンを評価して合否を返す。
    戻り値: {passed: bool, failed_cases: list[dict], message: str}
    """
    root = data_root or _data_root()
    puzzle_path = root / chapter_id / lesson_id / "puzzle.yaml"
    if not puzzle_path.exists():
        raise FileNotFoundError(f"パズルファイルが見つかりません: {puzzle_path}")

    puzzle = _load_yaml(puzzle_path)
    return evaluate_circuit(puzzle, connections, gate_placements)


def evaluate_circuit(
    puzzle: dict,
    connections: list[dict],
    gate_placements: list[dict],
) -> dict:
    """
    回路を評価して真理値表と照合する。
    puzzle の type が "sequential" の場合は順序回路として評価する。
    connections: [{from_id, from_port, to_id, to_port}, ...]
    gate_placements: [{id, type, x, y}, ...]
    """
    puzzle_type = puzzle.get("type", "combinational")
    if puzzle_type == "sequential":
        return _evaluate_sequential(puzzle, connections, gate_placements)
    return _evaluate_combinational(puzzle, connections, gate_placements)


def _evaluate_combinational(
    puzzle: dict,
    connections: list[dict],
    gate_placements: list[dict],
) -> dict:
    """組み合わせ回路を評価する"""
    target_rows = puzzle.get("target_truth_table", [])
    input_names = [i["name"] for i in puzzle.get("inputs", [])]
    output_names = [o["name"] for o in puzzle.get("outputs", [])]

    failed_cases: list[dict] = []

    for row in target_rows:
        input_vals: dict[str, int] = row["inputs"]
        expected_outputs: dict[str, int] = row["outputs"]

        actual_outputs = _simulate_circuit(
            input_vals, input_names, output_names, connections, gate_placements
        )

        for out_name in output_names:
            expected = expected_outputs.get(out_name, -1)
            actual = actual_outputs.get(out_name, -1)
            if actual != expected:
                failed_cases.append({
                    "inputs": input_vals,
                    "output": out_name,
                    "expected": expected,
                    "actual": actual,
                })

    passed = len(failed_cases) == 0
    if passed:
        message = "🎉 全パターン合格！回路が正しく動いています！"
    else:
        message = f"❌ {len(failed_cases)}パターンが不合格です。配線を見直してみましょう。"

    return {"passed": passed, "failed_cases": failed_cases, "message": message}


def _evaluate_sequential(
    puzzle: dict,
    connections: list[dict],
    gate_placements: list[dict],
) -> dict:
    """
    順序回路（DFFを含む）を評価する。
    target_truth_table は clock フィールドで順序付けられる。
    初期状態（clock=0）から順に DFF 状態を更新しながら検証する。
    """
    target_rows = sorted(
        puzzle.get("target_truth_table", []),
        key=lambda r: r.get("clock", 0),
    )
    input_names = [i["name"] for i in puzzle.get("inputs", [])]
    output_names = [o["name"] for o in puzzle.get("outputs", [])]

    # DFF ゲートの初期状態（すべて 0）
    dff_states: dict[str, int] = {
        g["id"]: 0
        for g in gate_placements
        if g.get("type") == "DFF"
    }

    failed_cases: list[dict] = []

    for row in target_rows:
        clock = row.get("clock", 0)
        input_vals: dict[str, int] = row["inputs"]
        expected_outputs: dict[str, int] = row["outputs"]

        # 現在の DFF 状態で回路を評価
        actual_outputs = _simulate_circuit(
            input_vals, input_names, output_names,
            connections, gate_placements, dff_states,
        )

        for out_name in output_names:
            expected = expected_outputs.get(out_name, -1)
            actual = actual_outputs.get(out_name, -1)
            if actual != expected:
                failed_cases.append({
                    "clock": clock,
                    "inputs": input_vals,
                    "output": out_name,
                    "expected": expected,
                    "actual": actual,
                })

        # クロックを1回進める: DFF の D 入力を次の Q に
        new_dff_states: dict[str, int] = {}
        for gate in gate_placements:
            if gate.get("type") != "DFF":
                continue
            gate_id = gate["id"]
            d_val = _get_dff_d_input(gate_id, input_vals, connections, gate_placements, dff_states)
            new_dff_states[gate_id] = d_val
        dff_states = new_dff_states if new_dff_states else dff_states

    passed = len(failed_cases) == 0
    if passed:
        message = "🎉 全クロックサイクル合格！順序回路が正しく動作しています！"
    else:
        message = f"❌ {len(failed_cases)}サイクルが不合格です。DFFの配線を確認してみましょう。"

    return {"passed": passed, "failed_cases": failed_cases, "message": message}


def _get_dff_d_input(
    gate_id: str,
    input_vals: dict[str, int],
    connections: list[dict],
    gate_placements: list[dict],
    dff_states: dict[str, int],
) -> int:
    """DFF の D 入力ポート（input_0）に接続されている値を取得する"""
    gates = {g["id"]: g for g in gate_placements}

    for c in connections:
        if c["to_id"] == gate_id and c.get("to_port", "input_0") == "input_0":
            return _get_node_output(
                c["from_id"], c.get("from_port", "output_0"),
                input_vals, connections, gate_placements, dff_states, set(),
            )
    return 0


def _get_node_output(
    node_id: str,
    port: str,
    input_vals: dict[str, int],
    connections: list[dict],
    gate_placements: list[dict],
    dff_states: dict[str, int],
    visited: set,
) -> int:
    """再帰的にノードの出力値を取得する"""
    # 入力ノード
    for name, val in input_vals.items():
        if node_id == f"input_{name}":
            return val

    if node_id in visited:
        return 0
    visited = visited | {node_id}

    gates = {g["id"]: g for g in gate_placements}
    gate = gates.get(node_id)
    if gate is None:
        return 0

    gate_type = gate.get("type", "")

    # DFF の出力は記憶された Q 値を返す（D 入力は見ない）
    if gate_type == "DFF":
        return dff_states.get(node_id, 0)

    # 他のゲートは入力ポートを再帰評価
    gate_inputs: list[int] = []
    for c in connections:
        if c["to_id"] == node_id:
            val = _get_node_output(
                c["from_id"], c.get("from_port", "output_0"),
                input_vals, connections, gate_placements, dff_states, visited,
            )
            gate_inputs.append(val)

    return _eval_gate(gate_type, gate_inputs) if gate_inputs else 0


def _simulate_circuit(
    input_vals: dict[str, int],
    input_names: list[str],
    output_names: list[str],
    connections: list[dict],
    gate_placements: list[dict],
    dff_states: Optional[dict[str, int]] = None,
) -> dict[str, int]:
    """
    接続情報から回路を評価する。
    dff_states: DFF ゲートの現在の Q 値（順序回路用）
    """
    dff_states = dff_states or {}
    node_values: dict[str, dict[str, int]] = {}

    for name in input_names:
        node_values[f"input_{name}"] = {"output_0": input_vals.get(name, 0)}

    gates = {g["id"]: g for g in gate_placements}

    def get_value(node_id: str, port: str, visited: set[str]) -> int:
        if node_id in node_values and port in node_values[node_id]:
            return node_values[node_id][port]

        for out_name in input_names:
            if node_id == f"input_{out_name}":
                return input_vals.get(out_name, 0)

        if node_id in visited:
            return 0
        visited = visited | {node_id}

        gate = gates.get(node_id)
        if gate is None:
            return 0

        gate_type = gate.get("type", "")

        # DFF の出力は記憶済みの Q 値（D 入力を評価しない）
        if gate_type == "DFF":
            q = dff_states.get(node_id, 0)
            node_values.setdefault(node_id, {})["output_0"] = q
            return q

        gate_inputs: list[int] = []
        for c in connections:
            if c["to_id"] == node_id:
                val = get_value(c["from_id"], c.get("from_port", "output_0"), visited)
                gate_inputs.append(val)

        if not gate_inputs:
            return 0

        result = _eval_gate(gate_type, gate_inputs)
        node_values.setdefault(node_id, {})["output_0"] = result
        return result

    outputs: dict[str, int] = {}
    for out_name in output_names:
        out_node_id = f"output_{out_name}"
        for c in connections:
            if c["to_id"] == out_node_id:
                val = get_value(c["from_id"], c.get("from_port", "output_0"), set())
                outputs[out_name] = val
                break
        else:
            outputs[out_name] = 0

    return outputs


def _eval_gate(gate_type: str, inputs: list[int]) -> int:
    """ゲートタイプと入力値リストから出力値を計算する"""
    if not inputs:
        return 0
    match gate_type.upper():
        case "AND":
            return 1 if all(v == 1 for v in inputs) else 0
        case "OR":
            return 1 if any(v == 1 for v in inputs) else 0
        case "NOT":
            return 1 if inputs[0] == 0 else 0
        case "XOR":
            result = 0
            for v in inputs:
                result ^= v
            return result
        case "NAND":
            return 0 if all(v == 1 for v in inputs) else 1
        case "NOR":
            return 0 if any(v == 1 for v in inputs) else 1
        case _:
            return 0


def _load_lesson_meta(
    lesson_dir: Path, chapter_id: str, lesson_id: str
) -> Optional[dict]:
    """レッスンディレクトリからメタ情報を構築する"""
    if not lesson_dir.exists():
        return None

    meta_path = lesson_dir / "meta.yaml"
    if meta_path.exists():
        meta = _load_yaml(meta_path)
    else:
        meta = {}

    meta.setdefault("id", lesson_id)
    meta.setdefault("title", lesson_id)
    meta["chapter_id"] = chapter_id
    meta["lesson_id"] = lesson_id
    meta["has_puzzle"] = (lesson_dir / "puzzle.yaml").exists()
    meta["has_quiz"] = (lesson_dir / "quiz.yaml").exists()
    meta["_dir"] = str(lesson_dir)
    return meta


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _render_markdown(text: str) -> str:
    """MarkdownテキストをHTMLに変換する"""
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "codehilite", "nl2br"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False}
        },
    )
    return md.convert(text)
