"""FastAPI アプリケーション定義"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fpga_study.content.loader import (
    check_puzzle_solution,
    check_quiz_answer,
    load_chapter,
    load_chapters,
    load_lesson,
    load_lessons,
)
from fpga_study.progress import (
    get_all_progress,
    get_badges,
    get_lesson_progress,
    init_db,
    save_puzzle_result,
    save_quiz_result,
)


def _static_dir() -> Path:
    try:
        ref = importlib.resources.files("fpga_study") / "static"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent / "static"


# ── リクエストモデル（モジュールレベルで定義） ──────────────────────

class QuizAnswerRequest(BaseModel):
    question_id: str
    answer_index: int


class QuizCompleteRequest(BaseModel):
    score: int
    total: int


class PuzzleCheckRequest(BaseModel):
    connections: list[dict[str, Any]]
    gate_placements: list[dict[str, Any]]


# ── アプリファクトリ ─────────────────────────────────────────────────

def create_app(db_path: Optional[Path] = None) -> FastAPI:
    """FastAPI アプリを生成して返す"""
    init_db(db_path)

    app = FastAPI(
        title="FPGAお勉強アプリ",
        description="完全な初心者向けFPGA学習ウェブアプリ",
        version="0.1.0",
    )

    static_dir = _static_dir()
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def root() -> HTMLResponse:
        index_path = static_dir / "index.html"
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    # ─── 章・レッスン ───────────────────────────────────

    @app.get("/api/chapters")
    async def api_chapters() -> list[dict]:
        chapters = load_chapters()
        for ch in chapters:
            ch.pop("_dir", None)
        return chapters

    @app.get("/api/chapters/{chapter_id}")
    async def api_chapter(chapter_id: str) -> dict:
        ch = load_chapter(chapter_id)
        if not ch:
            raise HTTPException(status_code=404, detail="章が見つかりません")
        ch.pop("_dir", None)
        return ch

    @app.get("/api/chapters/{chapter_id}/lessons")
    async def api_lessons(chapter_id: str) -> list[dict]:
        lessons = load_lessons(chapter_id)
        if not lessons:
            raise HTTPException(status_code=404, detail="章が見つかりません")
        for ls in lessons:
            ls.pop("_dir", None)
        return lessons

    @app.get("/api/chapters/{chapter_id}/lessons/{lesson_id}")
    async def api_lesson(chapter_id: str, lesson_id: str) -> dict:
        lesson = load_lesson(chapter_id, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="レッスンが見つかりません")
        lesson.pop("_dir", None)
        return lesson

    # ─── クイズ ───────────────────────────────────────────

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/quiz/check")
    async def api_quiz_check(
        chapter_id: str, lesson_id: str, req: QuizAnswerRequest
    ) -> dict:
        try:
            return check_quiz_answer(
                chapter_id, lesson_id, req.question_id, req.answer_index
            )
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/quiz/complete")
    async def api_quiz_complete(
        chapter_id: str, lesson_id: str, req: QuizCompleteRequest
    ) -> dict:
        return save_quiz_result(chapter_id, lesson_id, req.score, req.total, db_path)

    # ─── パズル ───────────────────────────────────────────

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/puzzle/check")
    async def api_puzzle_check(
        chapter_id: str, lesson_id: str, req: PuzzleCheckRequest
    ) -> dict:
        try:
            result = check_puzzle_solution(
                chapter_id, lesson_id, req.connections, req.gate_placements
            )
            if result["passed"]:
                save_puzzle_result(chapter_id, lesson_id, passed=True, db_path=db_path)
            return result
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # ─── 進捗・バッジ ─────────────────────────────────────

    @app.get("/api/progress")
    async def api_progress() -> dict:
        all_progress = get_all_progress(db_path)
        badges = get_badges(db_path)
        return {"progress": all_progress, "badges": badges}

    @app.get("/api/progress/{chapter_id}/{lesson_id}")
    async def api_lesson_progress(chapter_id: str, lesson_id: str) -> dict:
        return get_lesson_progress(chapter_id, lesson_id, db_path)

    return app
