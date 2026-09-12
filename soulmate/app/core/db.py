from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings


def ensure_sqlite_parent_dir(url: str) -> None:
    """SQLite 文件型 URL：确保库文件所在目录存在。

    为什么需要：``data/`` 目录被 gitignore（仓库只跟踪 ``data/.gitkeep``），
    新克隆或解压出来的副本里往往没有这个目录，而 SQLite **不会**自己创建目录，
    于是 ``alembic upgrade head`` 会直接失败：``unable to open database file``。
    这里把父目录补齐，让首次运行不再踩坑。
    """
    if not url.startswith("sqlite"):
        return

    _, separator, raw_path = url.partition(":///")
    if not separator:
        return

    # 去掉查询参数，例如 ?check_same_thread=false
    path = raw_path.split("?", 1)[0]
    if not path or path.startswith(":memory:"):
        return

    parent = Path(path).expanduser().parent
    if str(parent) in ("", "."):
        return
    parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> sa.Engine:
    ensure_sqlite_parent_dir(settings.database_url)
    return sa.create_engine(settings.database_url, future=True)


_engine = get_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(_engine) as session:
        yield session
