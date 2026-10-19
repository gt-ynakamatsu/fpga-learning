"""pytest 共通フィクスチャ"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fpga_study.server import create_app


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
