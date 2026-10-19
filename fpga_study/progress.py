"""学習進捗をSQLiteに保存・読み込みするモジュール"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _db_path() -> Path:
    base = Path.home() / ".fpga_study"
    base.mkdir(parents=True, exist_ok=True)
    return base / "progress.db"


def _get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """DBを初期化してテーブルを作成する"""
    conn = _get_conn(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lesson_progress (
                lesson_key TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL,
                lesson_id  TEXT NOT NULL,
                completed  INTEGER NOT NULL DEFAULT 0,
                quiz_score INTEGER NOT NULL DEFAULT 0,
                quiz_total INTEGER NOT NULL DEFAULT 0,
                puzzle_completed INTEGER NOT NULL DEFAULT 0,
                exercise_problems_done TEXT NOT NULL DEFAULT '[]',
                hdl_completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                badge_id   TEXT PRIMARY KEY,
                label      TEXT NOT NULL,
                earned_at  TEXT NOT NULL
            )
        """)
        # 既存DBにカラムを追加（マイグレーション）
        for col, ddl in [
            ("exercise_problems_done", "TEXT NOT NULL DEFAULT '[]'"),
            ("hdl_completed", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE lesson_progress ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass  # 既に存在する
    conn.close()


def get_all_progress(db_path: Optional[Path] = None) -> list[dict]:
    conn = _get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM lesson_progress").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_lesson_progress(
    chapter_id: str, lesson_id: str, db_path: Optional[Path] = None
) -> dict:
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    try:
        row = conn.execute(
            "SELECT * FROM lesson_progress WHERE lesson_key = ?", (key,)
        ).fetchone()
        if row:
            d = dict(row)
            d["exercise_problems_done"] = json.loads(d.get("exercise_problems_done") or "[]")
            return d
        return {
            "lesson_key": key,
            "chapter_id": chapter_id,
            "lesson_id": lesson_id,
            "completed": 0,
            "quiz_score": 0,
            "quiz_total": 0,
            "puzzle_completed": 0,
            "exercise_problems_done": [],
            "hdl_completed": 0,
            "completed_at": None,
            "updated_at": None,
        }
    finally:
        conn.close()


# ── 完了判定 ───────────────────────────────────────────────────────

def _check_completed(
    conn: sqlite3.Connection,
    key: str,
    all_problem_ids: list[str],
    has_hdl: bool,
    quiz_total: int,
) -> bool:
    """
    完了条件:
    1. quiz_total > 0 のとき: クイズが全問正解
    2. all_problem_ids がある場合: 練習問題が全問合格
    3. has_hdl=True のとき: HDL演習が PASS

    条件が何もない（練習問題なし・クイズなし・HDLなし）場合は完了にしない。
    パズルは完了条件に含まない（仕様未定）。
    """
    # 確認すべき条件が何もない場合は完了にしない
    if not all_problem_ids and quiz_total == 0 and not has_hdl:
        return False

    row = conn.execute(
        "SELECT * FROM lesson_progress WHERE lesson_key=?", (key,)
    ).fetchone()
    if not row:
        return False
    d = dict(row)

    if quiz_total > 0 and d["quiz_score"] < quiz_total:
        return False

    if all_problem_ids:
        done = set(json.loads(d.get("exercise_problems_done") or "[]"))
        if not all(pid in done for pid in all_problem_ids):
            return False

    if has_hdl and not d.get("hdl_completed", 0):
        return False

    return True


def _apply_completed(conn: sqlite3.Connection, key: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """UPDATE lesson_progress
               SET completed=1, completed_at=COALESCE(completed_at,?), updated_at=?
               WHERE lesson_key=?""",
            (now, now, key),
        )


def _ensure_row(
    conn: sqlite3.Connection, key: str, chapter_id: str, lesson_id: str, now: str
) -> None:
    existing = conn.execute(
        "SELECT lesson_key FROM lesson_progress WHERE lesson_key=?", (key,)
    ).fetchone()
    if not existing:
        with conn:
            conn.execute(
                """INSERT INTO lesson_progress
                   (lesson_key, chapter_id, lesson_id, completed,
                    quiz_score, quiz_total, puzzle_completed,
                    exercise_problems_done, hdl_completed, completed_at, updated_at)
                   VALUES (?, ?, ?, 0, 0, 0, 0, '[]', 0, NULL, ?)""",
                (key, chapter_id, lesson_id, now),
            )


# ── 各採点結果の保存 ───────────────────────────────────────────────

def save_quiz_result(
    chapter_id: str,
    lesson_id: str,
    score: int,
    total: int,
    all_problem_ids: list[str] = (),
    has_hdl: bool = False,
    db_path: Optional[Path] = None,
) -> dict:
    """クイズ結果を保存し、完了条件を再評価する"""
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        _ensure_row(conn, key, chapter_id, lesson_id, now)
        existing = conn.execute(
            "SELECT quiz_score FROM lesson_progress WHERE lesson_key=?", (key,)
        ).fetchone()
        # スコアが改善したときだけ更新
        if existing is None or score > existing["quiz_score"]:
            with conn:
                conn.execute(
                    "UPDATE lesson_progress SET quiz_score=?, quiz_total=?, updated_at=? WHERE lesson_key=?",
                    (score, total, now, key),
                )
        if _check_completed(conn, key, list(all_problem_ids), has_hdl, total):
            _apply_completed(conn, key)
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def save_practice_problem_result(
    chapter_id: str,
    lesson_id: str,
    problem_id: str,
    all_problem_ids: list[str],
    has_hdl: bool = False,
    quiz_total: int = 0,
    db_path: Optional[Path] = None,
) -> dict:
    """練習問題の1問の合格を記録し、完了条件を再評価する"""
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        _ensure_row(conn, key, chapter_id, lesson_id, now)
        row = conn.execute(
            "SELECT exercise_problems_done FROM lesson_progress WHERE lesson_key=?", (key,)
        ).fetchone()
        done = json.loads(row["exercise_problems_done"] or "[]")
        if problem_id not in done:
            done.append(problem_id)
        with conn:
            conn.execute(
                "UPDATE lesson_progress SET exercise_problems_done=?, updated_at=? WHERE lesson_key=?",
                (json.dumps(done), now, key),
            )
        if _check_completed(conn, key, list(all_problem_ids), has_hdl, quiz_total):
            _apply_completed(conn, key)
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def save_hdl_result(
    chapter_id: str,
    lesson_id: str,
    all_problem_ids: list[str] = (),
    quiz_total: int = 0,
    db_path: Optional[Path] = None,
) -> dict:
    """HDL演習の合格を記録し、完了条件を再評価する"""
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        _ensure_row(conn, key, chapter_id, lesson_id, now)
        with conn:
            conn.execute(
                "UPDATE lesson_progress SET hdl_completed=1, updated_at=? WHERE lesson_key=?",
                (now, key),
            )
        if _check_completed(conn, key, list(all_problem_ids), True, quiz_total):
            _apply_completed(conn, key)
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def save_puzzle_result(
    chapter_id: str,
    lesson_id: str,
    passed: bool,
    all_problem_ids: list[str] = (),
    has_hdl: bool = False,
    quiz_total: int = 0,
    db_path: Optional[Path] = None,
) -> dict:
    """
    パズル結果を保存する。

    注意: パズルの合格は完了条件には含まれない（仕様未定のため）。
    完了は「練習問題全問 + クイズ満点 + HDL演習（あるとき）」で判定する。
    パズルは puzzle_completed として別途記録するのみ。
    """
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        _ensure_row(conn, key, chapter_id, lesson_id, now)
        if passed:
            with conn:
                conn.execute(
                    "UPDATE lesson_progress SET puzzle_completed=1, updated_at=? WHERE lesson_key=?",
                    (now, key),
                )
        # パズル合格だけでは completed=1 にしない（仕様未定）
        # _check_completed を呼んで他条件が揃っていれば completed にする
        if _check_completed(conn, key, list(all_problem_ids), has_hdl, quiz_total):
            _apply_completed(conn, key)
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def get_badges(db_path: Optional[Path] = None) -> list[dict]:
    conn = _get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM badges ORDER BY earned_at").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _check_and_award_badges(
    conn: sqlite3.Connection, db_path: Optional[Path] = None
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute("SELECT * FROM lesson_progress").fetchall()
    progress_list = [dict(r) for r in rows]

    completed_count = sum(1 for p in progress_list if p["completed"])

    # 第N章マスターバッジは、「その章の全レッスンが完了」したときのみ付与
    # content から全レッスン ID を取得して照合する
    def _is_chapter_complete(chapter_id: str) -> bool:
        try:
            from fpga_study.content.loader import load_lessons as _load_ls
            all_lesson_ids = [ls["lesson_id"] for ls in (_load_ls(chapter_id) or [])]
        except Exception:
            all_lesson_ids = []
        if not all_lesson_ids:
            return False
        progress_map = {
            p["lesson_id"]: p["completed"]
            for p in progress_list
            if p["chapter_id"] == chapter_id
        }
        return all(progress_map.get(lid, 0) for lid in all_lesson_ids)

    ch1_completed = _is_chapter_complete("chapter01")

    badges_to_award: list[tuple[str, str]] = []
    if completed_count >= 1:
        badges_to_award.append(("first_lesson", "🌱 はじめの一歩"))
    if completed_count >= 3:
        badges_to_award.append(("three_lessons", "🔥 学習継続中"))
    if ch1_completed and progress_list:
        badges_to_award.append(("chapter01_complete", "🏆 第1章マスター"))

    existing = {
        r["badge_id"]
        for r in conn.execute("SELECT badge_id FROM badges").fetchall()
    }
    with conn:
        for badge_id, label in badges_to_award:
            if badge_id not in existing:
                conn.execute(
                    "INSERT INTO badges (badge_id, label, earned_at) VALUES (?, ?, ?)",
                    (badge_id, label, now),
                )


# 後方互換 alias（旧コードとの互換性）
def save_exercise_result(
    chapter_id: str,
    lesson_id: str,
    exercise_type: str = "practice",
    passed: bool = True,
    db_path: Optional[Path] = None,
) -> dict:
    """後方互換：新しいコードは save_practice_problem_result / save_hdl_result を使う"""
    if exercise_type == "hdl" and passed:
        return save_hdl_result(chapter_id, lesson_id, db_path=db_path)
    # practice の場合は何もしない（problem_id が必要なため）
    return get_lesson_progress(chapter_id, lesson_id, db_path)
