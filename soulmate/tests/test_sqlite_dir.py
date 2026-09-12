"""SQLite 库文件所在目录的自动创建。

背景：``data/`` 被 gitignore，新克隆/解压出来的副本里没有这个目录，
而 SQLite 不会自己创建目录 —— ``alembic upgrade head`` 会直接报
``unable to open database file``。这里把行为钉住。
"""

from __future__ import annotations

from app.core.db import ensure_sqlite_parent_dir


def test_creates_missing_parent_directory(tmp_path) -> None:
    target = tmp_path / "nested" / "data" / "soulmate.db"
    assert not target.parent.exists()

    ensure_sqlite_parent_dir(f"sqlite+pysqlite:///{target.as_posix()}")

    assert target.parent.is_dir()


def test_relative_path_is_supported(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    ensure_sqlite_parent_dir("sqlite+pysqlite:///./data/soulmate.db")

    assert (tmp_path / "data").is_dir()


def test_memory_database_is_ignored() -> None:
    # 不应抛错，也不应创建任何目录
    ensure_sqlite_parent_dir("sqlite+pysqlite:///:memory:")


def test_non_sqlite_url_is_ignored() -> None:
    # Postgres 之类的 URL 不该被当成文件路径处理
    ensure_sqlite_parent_dir("postgresql+psycopg://user:pw@localhost:5432/soulmate")


def test_existing_directory_is_left_alone(tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    marker = data_dir / "keep.txt"
    marker.write_text("x", encoding="utf-8")

    ensure_sqlite_parent_dir(f"sqlite+pysqlite:///{(data_dir / 'soulmate.db').as_posix()}")

    assert marker.read_text(encoding="utf-8") == "x"
