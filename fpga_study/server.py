"""FastAPI アプリケーション定義"""

from __future__ import annotations

import importlib.resources
import tempfile
from pathlib import Path
from typing import Any, Optional, Union

import asyncio
import concurrent.futures

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fpga_study.content.loader import (
    check_exercise_answer,
    check_puzzle_solution,
    check_quiz_answer,
    get_exercise_spec_path,
    load_chapter,
    load_chapters,
    load_exercise,
    load_lesson,
    load_lessons,
)
from fpga_study.content.lint import lint_hdl
from fpga_study.progress import (
    get_all_progress,
    get_badges,
    get_lesson_progress,
    init_db,
    save_hdl_result,
    save_practice_problem_result,
    save_puzzle_result,
    save_quiz_result,
)
from fpga_study.simulator import (
    DELTASIM_MIN_VERSION,
    DeltasimCLISimulator,
    check_deltasim_requirement,
)

# レビュー済み以上のステータスのみ公開（デフォルト）
_VISIBLE_STATUSES = {"reviewed", "published"}
_ALL_STATUSES = {"draft", "review", "reviewed", "published"}


def _static_dir() -> Path:
    try:
        ref = importlib.resources.files("fpga_study") / "static"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent / "static"


def _filter_lessons(lessons: list[dict], show_drafts: bool) -> list[dict]:
    if show_drafts:
        return lessons
    return [ls for ls in lessons if ls.get("status", "draft") in _VISIBLE_STATUSES]


def _filter_chapters(chapters: list[dict], show_drafts: bool) -> list[dict]:
    if show_drafts:
        return chapters
    return [ch for ch in chapters if ch.get("status", "draft") in _VISIBLE_STATUSES]


# ── リクエストモデル ──────────────────────────────────────────────────

class QuizAnswerRequest(BaseModel):
    question_id: str
    answer_index: int


class QuizCompleteRequest(BaseModel):
    score: int
    total: int


class PuzzleCheckRequest(BaseModel):
    connections: list[dict[str, Any]]
    gate_placements: list[dict[str, Any]]


class ExerciseCheckRequest(BaseModel):
    problem_id: str
    answer: Union[str, int, float]


class HdlGradeRequest(BaseModel):
    code: str


# ── アプリファクトリ ─────────────────────────────────────────────────

_grading_semaphore = asyncio.Semaphore(1)  # 同時採点1件制限


def create_app(
    db_path: Optional[Path] = None,
    show_drafts: bool = False,
) -> FastAPI:
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
        chapters = _filter_chapters(load_chapters(), show_drafts)
        for ch in chapters:
            ch.pop("_dir", None)
        return chapters

    @app.get("/api/chapters/{chapter_id}")
    async def api_chapter(chapter_id: str) -> dict:
        ch = load_chapter(chapter_id)
        if not ch:
            raise HTTPException(status_code=404, detail="章が見つかりません")
        _check_visible(ch.get("status"), "この章は現在公開されていません")
        ch.pop("_dir", None)
        return ch

    @app.get("/api/chapters/{chapter_id}/lessons")
    async def api_lessons(chapter_id: str) -> list[dict]:
        lessons = load_lessons(chapter_id)
        if not lessons:
            raise HTTPException(status_code=404, detail="章が見つかりません")
        lessons = _filter_lessons(lessons, show_drafts)
        for ls in lessons:
            ls.pop("_dir", None)
        return lessons

    def _check_visible(status: Optional[str], detail: str = "レッスンが見つかりません") -> None:
        """show_drafts=False のとき draft/review は 404"""
        if not show_drafts and status in ("draft", "review"):
            raise HTTPException(status_code=404, detail=detail)

    @app.get("/api/chapters/{chapter_id}/lessons/{lesson_id}")
    async def api_lesson(chapter_id: str, lesson_id: str) -> dict:
        lesson = load_lesson(chapter_id, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="レッスンが見つかりません")
        _check_visible(lesson.get("status"))
        # 演習データを追加（正解・ヒントは除去）
        exercise = load_exercise(chapter_id, lesson_id)
        if exercise:
            exercise.pop("_dir", None)
            for prob in exercise.get("problems", []):
                prob.pop("answer", None)       # 正解を返さない
                prob.pop("wrong_hint", None)   # 誤答ヒントは回答後のみ
        lesson["exercise"] = exercise
        # クイズから正解・解説を除去（回答後のみ返す）
        if lesson.get("quiz"):
            for q in lesson["quiz"].get("questions", []):
                q.pop("answer", None)
                q.pop("explanation", None)
        lesson.pop("_dir", None)
        return lesson

    # ─── クイズ ───────────────────────────────────────────

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/quiz/check")
    async def api_quiz_check(
        chapter_id: str, lesson_id: str, req: QuizAnswerRequest
    ) -> dict:
        lesson_for_check = load_lesson(chapter_id, lesson_id)
        if lesson_for_check:
            _check_visible(lesson_for_check.get("status"), "このレッスンは現在公開されていません")
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
        lesson_info = load_lesson(chapter_id, lesson_id)
        if lesson_info:
            _check_visible(lesson_info.get("status"), "このレッスンは現在公開されていません")
        exercise = load_exercise(chapter_id, lesson_id)
        all_prob_ids = [p["id"] for p in (exercise or {}).get("problems", [])]
        has_hdl = (lesson_info or {}).get("has_hdl_exercise", False)
        return save_quiz_result(
            chapter_id, lesson_id, req.score, req.total,
            all_prob_ids, has_hdl, db_path
        )

    # ─── 練習問題 (exercise) ─────────────────────────────

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/exercise/check")
    async def api_exercise_check(
        chapter_id: str, lesson_id: str, req: ExerciseCheckRequest
    ) -> dict:
        lesson = load_lesson(chapter_id, lesson_id)
        if lesson:
            _check_visible(lesson.get("status"), "このレッスンは現在公開されていません")
        try:
            result = check_exercise_answer(
                chapter_id, lesson_id, req.problem_id, req.answer
            )
            if result["correct"]:
                exercise = load_exercise(chapter_id, lesson_id)
                all_problem_ids = [p["id"] for p in (exercise or {}).get("problems", [])]
                lesson_info = load_lesson(chapter_id, lesson_id)
                has_hdl = (lesson_info or {}).get("has_hdl_exercise", False)
                quiz_total = len((lesson_info or {}).get("quiz", {}).get("questions", []))
                save_practice_problem_result(
                    chapter_id, lesson_id, req.problem_id,
                    all_problem_ids, has_hdl, quiz_total, db_path
                )
            # 正解を返さない
            result.pop("correct_answer", None)
            return result
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # ─── HDL 演習 ─────────────────────────────────────────

    @app.get("/api/deltasim/status")
    async def api_deltasim_status() -> dict:
        """deltasim のバージョン状況を返す"""
        ok, ver, msg = check_deltasim_requirement()
        return {
            "available": ok,
            "version": ver,
            "min_version": DELTASIM_MIN_VERSION,
            "message": msg,
        }

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/hdl/grade")
    async def api_hdl_grade(
        chapter_id: str, lesson_id: str, req: HdlGradeRequest
    ) -> dict:
        """HDL 演習コードを deltasim で採点し、lint ヒントと合わせて返す"""
        lesson_info = load_lesson(chapter_id, lesson_id)
        if lesson_info:
            _check_visible(lesson_info.get("status"), "このレッスンは現在公開されていません")

        exercise = load_exercise(chapter_id, lesson_id)
        if not exercise or exercise.get("type") != "hdl":
            raise HTTPException(status_code=404, detail="HDL演習が見つかりません")

        lint_hints = lint_hdl(req.code)

        ok, ver, ver_msg = check_deltasim_requirement()
        if not ok:
            return {
                "simulator_available": False,
                "simulator_version_ok": False,
                "version": ver,
                "message": ver_msg,
                "status": "SKIP",
                "cases": [],
                "errors": [],
                "lint_hints": lint_hints,
                "user_message": f"deltasim {DELTASIM_MIN_VERSION} 以上が必要です。\n{ver_msg}",
            }

        spec_path = get_exercise_spec_path(chapter_id, lesson_id)
        if not spec_path or not spec_path.exists():
            raise HTTPException(status_code=404, detail="spec.yaml が見つかりません")

        # 同時採点1件制限
        if _grading_semaphore.locked():
            return {
                "simulator_available": True,
                "simulator_version_ok": True,
                "version": ver,
                "message": ver_msg,
                "status": "BUSY",
                "cases": [],
                "errors": [],
                "lint_hints": lint_hints,
                "user_message": "採点中です。しばらく待ってからもう一度お試しください。",
            }

        async def _grade() -> dict:
            async with _grading_semaphore:
                with tempfile.TemporaryDirectory() as tmp:
                    code_path = Path(tmp) / "design.sv"
                    code_path.write_text(req.code, encoding="utf-8")
                    sim = DeltasimCLISimulator()
                    result = await run_in_threadpool(sim.run, [code_path], spec_path)

                if result.success:
                    exercise_info = load_exercise(chapter_id, lesson_id)
                    all_prob_ids = [p["id"] for p in (exercise_info or {}).get("problems", [])]
                    lesson_info2 = load_lesson(chapter_id, lesson_id)
                    q_total = len((lesson_info2 or {}).get("quiz", {}).get("questions", []))
                    save_hdl_result(
                        chapter_id, lesson_id, all_prob_ids, q_total, db_path
                    )

                # ケース名の日本語マッピング（exercise.yaml の case_descriptions）
                case_descriptions = exercise.get("case_descriptions", {})

                # ケースごとの結果（時刻を初心者向けに）
                cases_out = []
                for c in result.cases:
                    failed_checks = []
                    for ch in c.checks:
                        if ch.status == "PASS":
                            continue
                        offset_ns = ch.offset_ns or 0  # CheckResult.offset_ns (v0.2.1+)
                        if offset_ns:
                            loc = f"{ch.cycle}サイクル目のクロックの立ち上がりから{offset_ns}ns後"
                        else:
                            loc = f"{ch.cycle}サイクル目"
                        failed_checks.append({
                            "name": ch.name,
                            "signal": ch.signal,
                            "cycle": ch.cycle,
                            "offset_ns": offset_ns,
                            "location": loc,
                            "expected": ch.expected,
                            "actual": ch.actual,
                            "message": ch.message,
                        })
                    jp_name = case_descriptions.get(c.name, c.name)
                    cases_out.append({
                        "name": c.name,
                        "display_name": jp_name,
                        "status": c.status,
                        "failed_checks": failed_checks,
                        "message": c.message,
                    })

                # エラー（パスをファイル名のみに）
                errors_out = []
                for e in result.errors:
                    fname = Path(e.file).name if e.file else ""
                    errors_out.append({
                        "file": fname,
                        "line": e.line,
                        "severity": e.severity,
                        "message": e.message,
                        "code": e.code,
                    })

                return {
                    "simulator_available": True,
                    "simulator_version_ok": True,
                    "version": ver,
                    "message": ver_msg,
                    "status": result.status,
                    "cases": cases_out,
                    "errors": errors_out,
                    "lint_hints": lint_hints,
                    "user_message": result.user_message,
                    # 詳細：errors[] の code と message のみ（JSON全体や/tmpパスは出さない）
                    "error_detail": [
                        {"code": e.code, "message": e.message}
                        for e in result.errors
                    ] if result.errors else None,
                }

        return await _grade()

    # ─── パズル ───────────────────────────────────────────

    @app.post("/api/chapters/{chapter_id}/lessons/{lesson_id}/puzzle/check")
    async def api_puzzle_check(
        chapter_id: str, lesson_id: str, req: PuzzleCheckRequest
    ) -> dict:
        puzzle_lesson = load_lesson(chapter_id, lesson_id)
        if puzzle_lesson:
            _check_visible(puzzle_lesson.get("status"), "このレッスンは現在公開されていません")
        try:
            result = check_puzzle_solution(
                chapter_id, lesson_id, req.connections, req.gate_placements
            )
            if result["passed"]:
                exercise = load_exercise(chapter_id, lesson_id)
                all_prob_ids = [p["id"] for p in (exercise or {}).get("problems", [])]
                lesson_inf = load_lesson(chapter_id, lesson_id)
                has_hdl = (lesson_inf or {}).get("has_hdl_exercise", False)
                q_total = len((lesson_inf or {}).get("quiz", {}).get("questions", []))
                save_puzzle_result(
                    chapter_id, lesson_id, passed=True,
                    all_problem_ids=all_prob_ids, has_hdl=has_hdl,
                    quiz_total=q_total, db_path=db_path
                )
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
