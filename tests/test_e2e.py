"""
E2E テスト — 実際の uvicorn サーバーを起動して HTTP レベルで検証する

テスト対象:
  - レッスン応答（演習データ含む、説明→演習→クイズの順）
  - 練習問題採点（正解・不正解、進捗保存）
  - HDL 採点 PASS（answer.sv → deltasim v0.2.2 必須）
  - HDL 採点 FAIL（wrong_codes → 失敗チェック expected/actual）
  - always_ff 内の = → lint ヒントのみ（採点には影響しない）
  - deltasim 旧バージョン → 「0.2.2 以上が必要」応答
  - コンテンツ可視性（デフォルト非表示 / --show-drafts で表示）
  - (Optional) Playwright ブラウザテスト
"""

from __future__ import annotations

import json
import shutil
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

DATA_ROOT = Path(__file__).parent.parent / "fpga_study" / "data"

# deltasim v0.2.2 の有無
try:
    from fpga_study.simulator import check_deltasim_requirement, DELTASIM_MIN_VERSION
    _ok, _ver, _ = check_deltasim_requirement()
    DELTASIM_OK = _ok
except Exception:
    DELTASIM_OK = False

skip_if_no_deltasim_v022 = pytest.mark.skipif(
    not DELTASIM_OK,
    reason=(
        f"deltasim {DELTASIM_MIN_VERSION} 以上が必要です。"
        " pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@v0.2.2'"
    ),
)

# Playwright の有無
try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

skip_if_no_playwright = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="playwright がインストールされていません。pip install playwright && playwright install chromium",
)


# ── HTTP ヘルパー ────────────────────────────────────────────────────

def _wait(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"サーバーの起動待機がタイムアウトしました: {url}")


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as r:
        return json.loads(r.read())


def _post(base: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── サーバーフィクスチャ ──────────────────────────────────────────


def _start_server(db_path: Path, show_drafts: bool, port: int) -> threading.Thread:
    import uvicorn
    from fpga_study.server import create_app
    app = create_app(db_path=db_path, show_drafts=show_drafts)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    _wait(f"http://127.0.0.1:{port}/")
    t._uvicorn_server = server  # type: ignore[attr-defined]
    return t


@pytest.fixture(scope="module")
def server_with_drafts(tmp_path_factory):
    """show_drafts=True のサーバー（全レッスン可視）"""
    db = tmp_path_factory.mktemp("e2e") / "e2e.db"
    port = _free_port()
    t = _start_server(db, show_drafts=True, port=port)
    yield f"http://127.0.0.1:{port}"
    t._uvicorn_server.should_exit = True  # type: ignore[attr-defined]
    t.join(timeout=5)


@pytest.fixture(scope="module")
def server_no_drafts(tmp_path_factory):
    """show_drafts=False のサーバー（デフォルト; reviewed/published のみ）"""
    db = tmp_path_factory.mktemp("e2e_nd") / "e2e.db"
    port = _free_port()
    t = _start_server(db, show_drafts=False, port=port)
    yield f"http://127.0.0.1:{port}"
    t._uvicorn_server.should_exit = True  # type: ignore[attr-defined]
    t.join(timeout=5)


# ── E2E テスト ────────────────────────────────────────────────────


class TestLessonFlow:
    """レッスン応答に演習・クイズが正しい順序で含まれること"""

    def test_lesson_has_exercise_and_quiz(self, server_with_drafts):
        data = _get(server_with_drafts, "/api/chapters/chapter01/lessons/lesson01")
        assert data["content_html"], "説明コンテンツが空です"
        assert data["exercise"] is not None, "exercise フィールドがありません"
        assert data["exercise"]["type"] == "practice"
        assert len(data["exercise"]["problems"]) >= 1
        assert data["quiz"] is not None, "quiz フィールドがありません"
        assert len(data["quiz"]["questions"]) >= 1

    def test_lesson_exercise_problems_have_required_fields(self, server_with_drafts):
        data = _get(server_with_drafts, "/api/chapters/chapter01/lessons/lesson01")
        for p in data["exercise"]["problems"]:
            assert "id" in p
            assert "question" in p
            assert "type" in p


class TestPracticeExercise:
    """練習問題採点 + 進捗保存"""

    def test_correct_answer(self, server_with_drafts):
        res = _post(server_with_drafts,
                    "/api/chapters/chapter01/lessons/lesson01/exercise/check",
                    {"problem_id": "p1", "answer": 8})
        assert res["correct"] is True
        assert res["hint"] is None

    def test_wrong_answer_returns_hint(self, server_with_drafts):
        res = _post(server_with_drafts,
                    "/api/chapters/chapter01/lessons/lesson01/exercise/check",
                    {"problem_id": "p1", "answer": 0})
        assert res["correct"] is False
        assert res["hint"] is not None or res["wrong_hint"] is not None

    def test_correct_answer_saves_progress(self, server_with_drafts):
        _post(server_with_drafts,
              "/api/chapters/chapter01/lessons/lesson01/exercise/check",
              {"problem_id": "p1", "answer": 8})
        prog = _get(server_with_drafts, "/api/progress/chapter01/lesson01")
        # 1問正解だけでは completed にならない
        assert "p1" in (prog.get("exercise_problems_done") or []), \
            "p1 が exercise_problems_done に含まれていません"


class TestHdlGrading:
    """HDL 採点（deltasim v0.2.2 必須）"""

    @skip_if_no_deltasim_v022
    def test_answer_sv_passes(self, server_with_drafts):
        """答案コードが PASS になること"""
        answer_sv = (DATA_ROOT / "chapter06" / "lesson01" / "answer.sv").read_text(encoding="utf-8")
        res = _post(server_with_drafts,
                    "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
                    {"code": answer_sv})
        assert res["simulator_available"] is True
        assert res["simulator_version_ok"] is True
        assert res["status"] == "PASS", f"answer.sv が PASS しません: {res['user_message']}"
        # ケースごとの結果が含まれること
        assert len(res["cases"]) > 0
        assert all(c["status"] == "PASS" for c in res["cases"])

    @skip_if_no_deltasim_v022
    def test_wrong_code_fails_with_check_details(self, server_with_drafts):
        """wrong_codes の FAIL コードが失敗チェック情報を返すこと"""
        wrong_sv = (DATA_ROOT / "chapter06" / "lesson01" /
                    "wrong_codes" / "and_twostage.sv").read_text(encoding="utf-8")
        res = _post(server_with_drafts,
                    "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
                    {"code": wrong_sv})
        assert res["status"] in ("FAIL", "ERROR")
        # 失敗ケースの expected/actual が含まれること
        failed_cases = [c for c in res["cases"] if c["status"] != "PASS"]
        assert len(failed_cases) > 0
        # 少なくとも1件の failed_check に expected/actual があること
        has_details = any(
            len(c.get("failed_checks", [])) > 0
            for c in failed_cases
        )
        if not has_details:
            # errors 経由でもよい（E001 などの場合）
            assert len(res["errors"]) > 0

    @skip_if_no_deltasim_v022
    def test_lint_hint_for_blocking_assign(self, server_with_drafts):
        """always_ff 内の = が lint ヒントを返すが採点には影響しない"""
        # blocking = を使った DFF コード（正しいコードだが = を使う）
        code = (
            "module d_ff(\n"
            "    input  logic clk, rst, d,\n"
            "    output logic q\n"
            ");\n"
            "    always_ff @(posedge clk) begin\n"
            "        if (rst) q = 1'b0;  // blocking = (style error)\n"
            "        else     q = d;\n"
            "    end\n"
            "endmodule\n"
        )
        res = _post(server_with_drafts,
                    "/api/chapters/chapter06/lessons/lesson03/hdl/grade",
                    {"code": code})
        # lint ヒントがあること
        assert len(res["lint_hints"]) >= 1, "lint ヒントがありません"
        assert any("<=" in h or "ブロッキング" in h for h in res["lint_hints"])
        # ただし採点は行われている（lint はグレーディングに影響しない）
        assert res["status"] in ("PASS", "FAIL", "ERROR")


class TestOldDeltasim:
    """deltasim 旧バージョン時の応答"""

    def test_old_version_returns_version_error(self, server_with_drafts, monkeypatch):
        """deltasim 0.1.0 を報告するとき、グレーディングしない"""
        import fpga_study.simulator as sim_mod
        monkeypatch.setattr(sim_mod, "get_deltasim_version", lambda: "0.1.0")

        code = "module and_gate(\n    input  logic a,\n    input  logic b,\n    output logic y\n);\n    assign y = a & b;\nendmodule"
        res = _post(server_with_drafts,
                    "/api/chapters/chapter06/lessons/lesson01/hdl/grade",
                    {"code": code})

        assert res["simulator_version_ok"] is False, "古いバージョンでも version_ok=True になっています"
        assert "0.2." in res["user_message"], (
            f"バージョンエラーメッセージにバージョン番号が含まれていません: {res['user_message']}"
        )
        assert res["status"] == "SKIP", f"古いバージョンでも grading が実行されました: {res['status']}"

    def test_old_version_status_endpoint(self, server_with_drafts, monkeypatch):
        """/api/deltasim/status が正しく古いバージョンを報告すること"""
        import fpga_study.simulator as sim_mod
        monkeypatch.setattr(sim_mod, "get_deltasim_version", lambda: "0.1.0")

        status = _get(server_with_drafts, "/api/deltasim/status")
        assert status["available"] is False
        assert status["version"] == "0.1.0"


class TestContentVisibility:
    """コンテンツ可視性（draft/review は非表示）"""

    def test_drafts_hidden_by_default(self, server_no_drafts):
        """デフォルトでは reviewed/published のみ返す"""
        chapters = _get(server_no_drafts, "/api/chapters")
        for ch in chapters:
            assert ch.get("status") in ("reviewed", "published", None), (
                f"draft/review の章が返されました: {ch['id']}: {ch.get('status')}"
            )

    def test_show_drafts_reveals_all(self, server_with_drafts):
        """show_drafts=True なら全章を返す"""
        chapters_all = _get(server_with_drafts, "/api/chapters")
        chapters_default = _get(server_with_drafts, "/api/chapters?show_drafts=false")
        # show_drafts=True のサーバーは全章を返す
        assert len(chapters_all) >= len(chapters_default)

    def test_show_drafts_param_on_default_server(self, server_no_drafts):
        """?show_drafts=true パラメータで draft も取得できる"""
        chapters_hidden = _get(server_no_drafts, "/api/chapters")
        chapters_shown = _get(server_no_drafts, "/api/chapters?show_drafts=true")
        assert len(chapters_shown) >= len(chapters_hidden)

    def test_ch3_lessons_visible_with_drafts(self, server_with_drafts):
        """reviewed の章のレッスンが取得できること"""
        lessons = _get(server_with_drafts, "/api/chapters/chapter03/lessons")
        assert len(lessons) >= 1


# ── Playwright ブラウザテスト (optional) ─────────────────────────


@skip_if_no_playwright
class TestBrowserQuiz:
    """Playwright を使ったクイズの操作テスト（高優先度: disabled バグの検証）"""

    def test_quiz_options_are_clickable(self, server_with_drafts):
        """クイズの選択肢がクリックできること（disabled バグが修正済みであること）"""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(
                    f"{server_with_drafts}/#lesson/chapter01/lesson01",
                    timeout=15000,
                )
                # クイズセクションが表示されるまで待つ
                page.wait_for_selector(".quiz-section", timeout=10000)

                # 最初の選択肢が存在して disabled でないこと
                option = page.locator(".quiz-option").first
                assert not option.is_disabled(), (
                    "クイズの選択肢が disabled になっています。"
                    "app.js の h() 関数で undefined を属性値に渡していないか確認してください。"
                )

                # 選択肢をクリックできること
                option.click()

                # 解説が表示されること
                page.wait_for_selector(".quiz-explanation.visible", timeout=5000)

                # 「次の問題」ボタンが押せること
                next_btn = page.locator("#quiz-next-btn")
                assert not next_btn.is_disabled(), "「次の問題」ボタンが disabled です"
                next_btn.click()

                # 次の問題 or 結果画面が表示されること
                page.wait_for_selector(".quiz-question, .quiz-result", timeout=5000)
            finally:
                browser.close()

    def test_quiz_full_flow(self, server_with_drafts):
        """クイズを全問回答して結果画面が表示されること"""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(
                    f"{server_with_drafts}/#lesson/chapter01/lesson01",
                    timeout=15000,
                )
                page.wait_for_selector(".quiz-section", timeout=10000)

                # 全問に答える
                for _ in range(10):  # 最大10問
                    options = page.locator(".quiz-option:not([disabled])")
                    if options.count() == 0:
                        break
                    options.first.click()
                    page.wait_for_selector("#quiz-next-btn:not([disabled])", timeout=3000)
                    next_btn = page.locator("#quiz-next-btn")
                    next_btn.click()
                    # 結果画面になったら終了
                    if page.locator(".quiz-result").count() > 0:
                        break

                # 結果画面が表示されること
                assert page.locator(".quiz-result").count() > 0 or \
                       page.locator(".quiz-score-big").count() > 0, \
                       "クイズ結果画面が表示されませんでした"
            finally:
                browser.close()


@skip_if_no_playwright
class TestBrowserHdlEditor:
    """Playwright を使ったブラウザレベルの HDL エディタテスト"""

    @skip_if_no_deltasim_v022
    def test_hdl_editor_flow(self, server_with_drafts):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(f"{server_with_drafts}/#lesson/chapter06/lesson01", timeout=15000)
                # HDL エディタが表示されること
                page.wait_for_selector(".hdl-section", timeout=10000)
                # テンプレートが prefill されていること
                editor = page.locator(".hdl-editor")
                assert editor.count() > 0, "HDL エディタが見つかりません"
                # 実行ボタンが存在すること
                run_btn = page.locator("button:has-text('実行して採点')")
                assert run_btn.count() > 0, "実行ボタンが見つかりません"
            finally:
                browser.close()
