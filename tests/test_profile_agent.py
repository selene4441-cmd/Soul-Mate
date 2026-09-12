from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.agents.profile_agent import update_user_profile_from_events
from app.models import BehaviorEvent, BehaviorEventType, Profile, User


@dataclass
class FakeClient:
    chat_model: str = "gpt-5.2"
    embedding_model: str = "fake-embed"
    summarize_calls: int = 0
    embed_calls: int = 0

    def summarize_hidden_traits(self, *, text: str) -> tuple[str, dict]:
        self.summarize_calls += 1
        # Keep it under 200 chars and paragraph-like.
        return ("他更偏好稳定、节奏清晰的互动，停留更久时代表投入；对高频目标更有兴趣，"
                "遇到不确定会先观察再表达，信任建立后会更主动。", {"total_tokens": 10})

    def embed(self, *, text: str) -> tuple[list[float], dict]:
        self.embed_calls += 1
        return [0.1, 0.2, 0.3, 0.4], {"total_tokens": 5}


def test_profile_agent_caching(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.commit()

    session.add_all(
        [
            BehaviorEvent(
                user_id=user.id,
                event_type=BehaviorEventType.BROWSE,
                target_id="card:1",
                duration_ms=200,
            ),
            BehaviorEvent(
                user_id=user.id,
                event_type=BehaviorEventType.DWELL,
                target_id="profile:2",
                duration_ms=5000,
            ),
        ]
    )
    session.commit()

    client = FakeClient()
    updated = update_user_profile_from_events(user_id=user.id, session=session, client=client)
    assert updated is True
    assert client.summarize_calls == 1
    assert client.embed_calls == 1

    profile = session.get(Profile, user.id)
    assert profile is not None
    assert profile.summary
    assert len(profile.summary) <= 200
    assert profile.embedding is not None
    assert profile.source_hash

    # Second run with unchanged events should hit cache.
    updated2 = update_user_profile_from_events(user_id=user.id, session=session, client=client)
    assert updated2 is False
    assert client.summarize_calls == 1
    assert client.embed_calls == 1

    # Add a new event -> cache miss.
    session.add(
        BehaviorEvent(
            user_id=user.id,
            event_type=BehaviorEventType.SWIPE,
            target_id="card:2",
            duration_ms=80,
        )
    )
    session.commit()

    updated3 = update_user_profile_from_events(user_id=user.id, session=session, client=client)
    assert updated3 is True
    assert client.summarize_calls == 2
    assert client.embed_calls == 2


def test_profile_agent_requires_consent(session: Session) -> None:
    user = User(consent=False)
    session.add(user)
    session.commit()

    client = FakeClient()
    try:
        update_user_profile_from_events(user_id=user.id, session=session, client=client)
    except PermissionError:
        pass
    else:
        raise AssertionError("expected PermissionError")

