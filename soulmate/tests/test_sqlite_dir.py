"""SQLite 库文件所在目录的自动创建。

背景：``data/`` 被 gitignore，新克隆/解压出来的副本里没有这个目录，
而 SQLite 不会自己创建目录 —— ``alembic upgrade head`` 会直接报
``unable to open database file``。这里把行为钉住。

注意：本仓库的 pytest.ini 带 ``-p no:tmpdir``，因此 **不能**用 ``tmp_path`` 夹具，
这里用 ``tempfile`` 自己建临时目录。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.db import ensure_sqlite_parent_dir


@pytest.fixture()
def workdir() -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix="sqlite-dir-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_creates_missing_parent_directory(workdir: Path) -> None:
    target = workdir / "nested" / "data" / "soulmate.db"
    assert not target.parent.exists()

    ensure_sqlite_parent_dir(f"sqlite+pysqlite:///{target.as_posix()}")

    assert target.parent.is_dir()


def test_relative_path_is_supported(workdir: Path) -> None:
    previous = os.getcwd()
    os.chdir(workdir)
    try:
        ensure_sqlite_parent_dir("sqlite+pysqlite:///./data/soulmate.db")
        assert (workdir / "data").is_dir()
    finally:
        os.chdir(previous)


def test_memory_database_is_ignored() -> None:
    # 不应抛错，也不应创建任何目录
    ensure_sqlite_parent_dir("sqlite+pysqlite:///:memory:")


def test_non_sqlite_url_is_ignored(workdir: Path) -> None:
    # Postgres 之类的 URL 不该被当成文件路径处理
    ensure_sqlite_parent_dir("postgresql+psycopg://user:pw@localhost:5432/soulmate")
    assert list(workdir.iterdir()) == []


def test_existing_directory_is_left_alone(workdir: Path) -> None:
    data_dir = workdir / "data"
    data_dir.mkdir()
    marker = data_dir / "keep.txt"
    marker.write_text("x", encoding="utf-8")

    ensure_sqlite_parent_dir(f"sqlite+pysqlite:///{(data_dir / 'soulmate.db').as_posix()}")

    assert marker.read_text(encoding="utf-8") == "x"
