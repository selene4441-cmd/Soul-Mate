from __future__ import annotations

import sqlalchemy as sa
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Base,
    BehaviorEvent,
    BehaviorEventType,
    Belief,
    Elicitation,
    ElicitationKind,
    Profile,
    Response,
    User,
)


def test_users_consent_field_persists(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.commit()

    loaded = session.get(User, user.id)
    assert loaded is not None
    assert loaded.consent is True


def test_behavior_events_created_at_index_exists() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    inspector = sa.inspect(engine)
    indexes = inspector.get_indexes("behavior_events")
    assert any(idx["column_names"] == ["created_at"] for idx in indexes)


def test_behavior_events_insert(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.flush()

    event = BehaviorEvent(user_id=user.id, event_type=BehaviorEventType.BROWSE, duration_ms=1200)
    session.add(event)
    session.commit()

    loaded = session.get(BehaviorEvent, event.id)
    assert loaded is not None
    assert loaded.event_type == BehaviorEventType.BROWSE
    assert loaded.duration_ms == 1200


def test_elicitations_options_json_roundtrip(session: Session) -> None:
    elicitation = Elicitation(
        question="Choose one",
        options={"a": "A", "b": "B"},
        kind=ElicitationKind.SINGLE_CHOICE,
    )
    session.add(elicitation)
    session.commit()

    loaded = session.get(Elicitation, elicitation.id)
    assert loaded is not None
    assert loaded.options == {"a": "A", "b": "B"}


def test_responses_insert(session: Session) -> None:
    user = User(consent=True)
    elicitation = Elicitation(
        question="Choose one",
        options=["A", "B"],
        kind=ElicitationKind.SINGLE_CHOICE,
    )
    session.add_all([user, elicitation])
    session.flush()

    response = Response(
        user_id=user.id,
        elicitation_id=elicitation.id,
        choice="A",
        reaction_time_ms=350,
    )
    session.add(response)
    session.commit()

    loaded = session.get(Response, response.id)
    assert loaded is not None
    assert loaded.choice == "A"
    assert loaded.reaction_time_ms == 350


def test_profiles_embedding_binary(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.flush()

    profile = Profile(user_id=user.id, summary="hello", embedding=b"\x00\x01\x02")
    session.add(profile)
    session.commit()

    loaded = session.get(Profile, user.id)
    assert loaded is not None
    assert loaded.embedding == b"\x00\x01\x02"


def test_beliefs_confidence_range_enforced(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.flush()

    ok = Belief(user_id=user.id, hypothesis="h1", confidence=0.7)
    session.add(ok)
    session.commit()

    bad = Belief(user_id=user.id, hypothesis="h2", confidence=1.2)
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
