from __future__ import annotations

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from app.agents.relationship_store import (
    load_relationship_posterior,
    update_relationship_from_signals,
)
from app.models import Relationship, RelationshipSignal, User


def test_alembic_upgrade_head_on_empty_db_creates_relationship_tables(
    scratch_dir, monkeypatch
) -> None:
    db_path = scratch_dir / "alembic-empty-upgrade.db"
    url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    engine = sa.create_engine(url, future=True)
    inspector = sa.inspect(engine)
    names = set(inspector.get_table_names())
    assert "relationships" in names
    assert "relationship_signals" in names
    assert "conversations" in names
    assert "messages" in names

    cols = {c["name"] for c in inspector.get_columns("users")}
    assert "consent_scopes" in cols


def test_relationship_posterior_replays_from_signals(session: Session) -> None:
    u1 = User(consent=True)
    u2 = User(consent=True)
    session.add_all([u1, u2])
    session.flush()

    rel = Relationship(user_a=u1.id, user_b=u2.id, status="dating", alpha=1.0, beta=1.0, summary="")
    session.add(rel)
    session.flush()

    session.add_all(
        [
            RelationshipSignal(
                relationship_id=rel.id,
                source="test",
                kind="shared_topic",
                content="互相主动联系",
                weight=2.0,
            ),
            RelationshipSignal(
                relationship_id=rel.id,
                source="test",
                kind="conflict",
                content="沟通中断",
                weight=1.0,
            ),
            RelationshipSignal(
                relationship_id=rel.id,
                source="test",
                kind="uncertain",
                content="有点犹豫",
                weight=5.0,
            ),
        ]
    )
    session.commit()

    posterior = load_relationship_posterior(session, relationship_id=rel.id)
    assert posterior.alpha == 1.0 + 2.0
    assert posterior.beta == 1.0 + 1.0

    updated = update_relationship_from_signals(session, relationship_id=rel.id)
    assert updated.alpha == posterior.alpha
    assert updated.beta == posterior.beta
