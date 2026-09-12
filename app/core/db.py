from __future__ import annotations

from collections.abc import Generator

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings


def get_engine() -> sa.Engine:
    return sa.create_engine(settings.database_url, future=True)


_engine = get_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(_engine) as session:
        yield session

