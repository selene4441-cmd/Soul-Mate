from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str, *, echo: bool = False) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    return create_engine(url, echo=echo, future=True, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def ensure_schema(engine: Engine) -> None:
    """Create tables and add columns that older SQLite databases may be missing."""
    from . import models  # noqa: F401  # ensure XhsUser is registered on Base.metadata

    Base.metadata.create_all(engine)

    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(xhs_users)"))}
        for column, ddl in (("last_refreshed_at", "DATETIME"), ("refresh_error", "TEXT")):
            if column not in existing:
                conn.execute(text(f"ALTER TABLE xhs_users ADD COLUMN {column} {ddl}"))