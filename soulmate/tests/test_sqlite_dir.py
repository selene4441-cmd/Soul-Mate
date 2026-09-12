"""SQLite 库文件所在目录的自动创建。

背景：``data/`` 被 gitignore，新克隆/解压出来的副本里没有这个目录，
而 SQLite 不会自己创建目录 —— ``alembic upgrade head`` 会直接报
``unable to open database file``。这里把行为钉住。

注意两条本仓库的约束：
1. ``pytest.ini`` 带 ``-p no:tmpdir``，**不能**用 ``tmp_path`` 夹具；
2. 因此统一用 conftest 里既有的 ``scratch_dir``（``data/artifacts/run-*``），
   而不是 ``tempfile`` —— 后者落在系统临时目录，在受限环境里可能不可写。
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.db import ensure_sqlite_parent_dir


def test_creates_missing_parent_directory(scratch_dir: Path) -> None:
    target = scratch_dir / "nested" / "data" / "soulmate.db"
    assert not target.parent.exists()

    ensure_sqlite_parent_dir(f"sqlite+pysqlite:///{target.as_posix()}")

    assert target.parent.is_dir()


def test_relative_path_is_supported(scratch_dir: Path) -> None:
    # scratch_dir 是相对路径，chdir 之后就失效了，所以先取绝对路径
    target = scratch_dir.resolve()
    previous = os.getcwd()
    os.chdir(target)
    try:
        ensure_sqlite_parent_dir("sqlite+pysqlite:///./data/soulmate.db")
        assert (target / "data").is_dir()
    finally:
        os.chdir(previous)


def test_memory_database_is_ignored(scratch_dir: Path) -> None:
    # 不应抛错，也不应创建任何目录
    ensure_sqlite_parent_dir("sqlite+pysqlite:///:memory:")
    assert list(scratch_dir.iterdir()) == []


def test_non_sqlite_url_is_ignored(scratch_dir: Path) -> None:
    # Postgres 之类的 URL 不该被当成文件路径处理
    ensure_sqlite_parent_dir("postgresql+psycopg://user:pw@localhost:5432/soulmate")
    assert list(scratch_dir.iterdir()) == []


def test_existing_directory_is_left_alone(scratch_dir: Path) -> None:
    data_dir = scratch_dir / "data"
    data_dir.mkdir()
    marker = data_dir / "keep.txt"
    marker.write_text("x", encoding="utf-8")

    ensure_sqlite_parent_dir(f"sqlite+pysqlite:///{(data_dir / 'soulmate.db').as_posix()}")

    assert marker.read_text(encoding="utf-8") == "x"
