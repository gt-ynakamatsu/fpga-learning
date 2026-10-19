"""学習進捗をSQLiteに保存・読み込みするモジュール"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _db_path() -> Path:
    """進捗データの保存先 (ユーザーホーム配下)"""
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
    conn.close()


def get_all_progress(db_path: Optional[Path] = None) -> list[dict]:
    """全レッスンの進捗を返す"""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM lesson_progress").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_lesson_progress(
    chapter_id: str, lesson_id: str, db_path: Optional[Path] = None
) -> dict:
    """特定レッスンの進捗を返す。未記録なら初期値を返す"""
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    try:
        row = conn.execute(
            "SELECT * FROM lesson_progress WHERE lesson_key = ?", (key,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "lesson_key": key,
            "chapter_id": chapter_id,
            "lesson_id": lesson_id,
            "completed": 0,
            "quiz_score": 0,
            "quiz_total": 0,
            "puzzle_completed": 0,
            "completed_at": None,
            "updated_at": None,
        }
    finally:
        conn.close()


def _is_lesson_fully_complete(conn, chapter_id: str, lesson_id: str) -> bool:
    """練習問題＋クイズ（＋HDL演習があれば）の全合格を確認する"""
    key = f"{chapter_id}/{lesson_id}"
    row = conn.execute(
        "SELECT * FROM lesson_progress WHERE lesson_key = ?", (key,)
    ).fetchone()
    if not row:
        return False
    d = dict(row)
    # クイズが満点のこと
    if d["quiz_total"] > 0 and d["quiz_score"] < d["quiz_total"]:
        return False
    return True


def save_quiz_result(
    chapter_id: str,
    lesson_id: str,
    score: int,
    total: int,
    db_path: Optional[Path] = None,
) -> dict:
    """クイズ結果を保存し、全問正解かつ練習問題完了ならcompletedにする"""
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()
    completed = 1 if score == total else 0
    completed_at = now if completed else None

    try:
        existing = conn.execute(
            "SELECT * FROM lesson_progress WHERE lesson_key = ?", (key,)
        ).fetchone()

        with conn:
            if existing:
                # 既存スコアより良い場合のみ更新
                if score > existing["quiz_score"]:
                    conn.execute(
                        """UPDATE lesson_progress
                           SET quiz_score=?, quiz_total=?, completed=?,
                               completed_at=COALESCE(completed_at, ?), updated_at=?
                           WHERE lesson_key=?""",
                        (score, total, max(completed, existing["completed"]),
                         completed_at, now, key),
                    )
            else:
                conn.execute(
                    """INSERT INTO lesson_progress
                       (lesson_key, chapter_id, lesson_id, completed,
                        quiz_score, quiz_total, puzzle_completed, completed_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                    (key, chapter_id, lesson_id, completed,
                     score, total, completed_at, now),
                )
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def save_puzzle_result(
    chapter_id: str,
    lesson_id: str,
    passed: bool,
    db_path: Optional[Path] = None,
) -> dict:
    """パズル完了状態を保存する"""
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        existing = conn.execute(
            "SELECT * FROM lesson_progress WHERE lesson_key = ?", (key,)
        ).fetchone()

        puzzle_completed = 1 if passed else 0
        with conn:
            if existing:
                if passed:
                    conn.execute(
                        """UPDATE lesson_progress
                           SET puzzle_completed=1, completed=1,
                               completed_at=COALESCE(completed_at, ?), updated_at=?
                           WHERE lesson_key=?""",
                        (now, now, key),
                    )
            else:
                completed = 1 if passed else 0
                conn.execute(
                    """INSERT INTO lesson_progress
                       (lesson_key, chapter_id, lesson_id, completed,
                        quiz_score, quiz_total, puzzle_completed, completed_at, updated_at)
                       VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)""",
                    (key, chapter_id, lesson_id, completed,
                     puzzle_completed, now if passed else None, now),
                )
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def save_exercise_result(
    chapter_id: str,
    lesson_id: str,
    exercise_type: str = "practice",
    passed: bool = True,
    db_path: Optional[Path] = None,
) -> dict:
    """
    演習結果を保存する。
    exercise_type: "practice" (練習問題) または "hdl" (HDL演習)
    """
    conn = _get_conn(db_path)
    key = f"{chapter_id}/{lesson_id}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        existing = conn.execute(
            "SELECT * FROM lesson_progress WHERE lesson_key = ?", (key,)
        ).fetchone()

        with conn:
            if existing:
                if passed:
                    conn.execute(
                        """UPDATE lesson_progress
                           SET completed=1,
                               completed_at=COALESCE(completed_at, ?), updated_at=?
                           WHERE lesson_key=?""",
                        (now, now, key),
                    )
            else:
                conn.execute(
                    """INSERT INTO lesson_progress
                       (lesson_key, chapter_id, lesson_id, completed,
                        quiz_score, quiz_total, puzzle_completed, completed_at, updated_at)
                       VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?)""",
                    (key, chapter_id, lesson_id, 1 if passed else 0,
                     now if passed else None, now),
                )
        _check_and_award_badges(conn, db_path)
        return get_lesson_progress(chapter_id, lesson_id, db_path)
    finally:
        conn.close()


def get_badges(db_path: Optional[Path] = None) -> list[dict]:
    """獲得済みバッジ一覧を返す"""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM badges ORDER BY earned_at").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _check_and_award_badges(
    conn: sqlite3.Connection, db_path: Optional[Path] = None
) -> None:
    """進捗に応じてバッジを付与する"""
    now = datetime.now(timezone.utc).isoformat()

    rows = conn.execute("SELECT * FROM lesson_progress").fetchall()
    progress_list = [dict(r) for r in rows]

    completed_count = sum(1 for p in progress_list if p["completed"])
    ch1_completed = all(
        p["completed"] for p in progress_list if p["chapter_id"] == "chapter01"
    )

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
