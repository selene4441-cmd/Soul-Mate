from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Base, BehaviorEvent, Elicitation, Profile, Response, User
from scripts import gen_synthetic


def _sqlite_url(path: Path) -> str:
    # SQLAlchemy expects forward slashes and absolute path.
    return "sqlite+pysqlite:///" + str(path.resolve()).replace("\\", "/")


def test_gen_synthetic_idempotent(scratch_dir: Path, monkeypatch) -> None:
    db_path = scratch_dir / "synthetic.db"
    url = _sqlite_url(db_path)
    monkeypatch.setenv("DATABASE_URL", url)

    engine = sa.create_engine(url, future=True)
    Base.metadata.create_all(engine)

    args = ["--users", "5", "--min-events", "3", "--max-events", "7", "--cards", "2", "--seed", "123", "--no-llm"]

    assert gen_synthetic.main(args) == 0
    with Session(engine) as session:
        users1 = session.execute(sa.select(sa.func.count()).select_from(User)).scalar_one()
        cards1 = session.execute(sa.select(sa.func.count()).select_from(Elicitation)).scalar_one()
        profiles1 = session.execute(sa.select(sa.func.count()).select_from(Profile)).scalar_one()
        events1 = session.execute(sa.select(sa.func.count()).select_from(BehaviorEvent)).scalar_one()
        responses1 = session.execute(sa.select(sa.func.count()).select_from(Response)).scalar_one()

        assert users1 == 5
        assert cards1 == 2
        assert profiles1 == 5
        assert responses1 == 10  # users * cards
        assert events1 >= 5 * 3

    # Second run should not change totals.
    assert gen_synthetic.main(args) == 0
    with Session(engine) as session:
        users2 = session.execute(sa.select(sa.func.count()).select_from(User)).scalar_one()
        cards2 = session.execute(sa.select(sa.func.count()).select_from(Elicitation)).scalar_one()
        profiles2 = session.execute(sa.select(sa.func.count()).select_from(Profile)).scalar_one()
        events2 = session.execute(sa.select(sa.func.count()).select_from(BehaviorEvent)).scalar_one()
        responses2 = session.execute(sa.select(sa.func.count()).select_from(Response)).scalar_one()

        assert (users2, cards2, profiles2, events2, responses2) == (users1, cards1, profiles1, events1, responses1)

