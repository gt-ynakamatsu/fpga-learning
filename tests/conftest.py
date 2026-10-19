"""pytest 共通フィクスチャ"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fpga_study.server import create_app


def pytest_configure(config: pytest.Config) -> None:
    """REQUIRE_DELTASIM=1 のとき、deltasim v0.2.1 以上がなければ即 FAIL"""
    if os.environ.get("REQUIRE_DELTASIM", "0") != "1":
        return

    install_hint = "pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@v0.2.1'"

    try:
        from fpga_study.simulator import get_deltasim_version
        ver = get_deltasim_version()
    except Exception as e:
        pytest.exit(f"REQUIRE_DELTASIM=1: deltasim バージョン取得失敗: {e}\n{install_hint}", returncode=1)
        return

    if ver is None:
        pytest.exit(
            f"REQUIRE_DELTASIM=1: deltasim がインストールされていません。\n{install_hint}",
            returncode=1,
        )
        return

    try:
        parts = tuple(int(x) for x in ver.split("."))
    except ValueError:
        pytest.exit(f"REQUIRE_DELTASIM=1: バージョン解析失敗: {ver!r}", returncode=1)
        return

    if parts < (0, 2, 1):
        pytest.exit(
            f"REQUIRE_DELTASIM=1: deltasim {ver} < 0.2.1。\n{install_hint}",
            returncode=1,
        )


@pytest.fixture()
def data_root() -> Path:
    """本番教材ディレクトリを返す"""
    return Path(__file__).parent.parent / "fpga_study" / "data"


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """テスト用一時SQLiteファイルパスを返す（初期化済み）"""
    from fpga_study.progress import init_db
    db = tmp_path / "test.db"
    init_db(db)
    return db


@pytest.fixture()
def client(tmp_db: Path) -> TestClient:
    """テスト用FastAPIクライアント"""
    app = create_app(db_path=tmp_db)
    return TestClient(app)
