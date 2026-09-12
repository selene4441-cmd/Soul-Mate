from __future__ import annotations

from array import array
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.agents.match_agent import match_user
from app.models import Profile, User


def _emb(values: list[float]) -> bytes:
    return array("f", values).tobytes()


@dataclass
class FakeRerankClient:
    chat_model: str = "gpt-5.2"
    calls: int = 0

    def rerank(self, *, user_summary: str, candidates: list[tuple[int, float, str]]):
        self.calls += 1
        # Deterministic: order by retrieval cosine, but squash to 0-1.
        ranked: list[dict[str, Any]] = []
        for uid, sim, summary in sorted(candidates, key=lambda x: (-x[1], x[0])):
            score = max(0.0, min(1.0, (float(sim) + 1.0) / 2.0))
            ranked.append(
                {
                    "user_id": uid,
                    "score": score,
                    "reasons": [f"你「{user_summary[:8]}」与TA「{summary[:8]}」有呼应。"],
                }
            )
        return ranked, {"total_tokens": 1}


def test_match_agent_caches_same_pair(session: Session) -> None:
    u1 = User(consent=True)
    u2 = User(consent=True)
    u3 = User(consent=True)
    session.add_all([u1, u2, u3])
    session.flush()

    session.add_all(
        [
            Profile(
                user_id=u1.id,
                summary="A用户画像：偏稳定，慢热。",
                embedding=_emb([1.0, 0.0]),
                source_hash="h1",
            ),
            Profile(
                user_id=u2.id,
                summary="B用户画像：也偏稳定，愿意沟通。",
                embedding=_emb([0.9, 0.1]),
                source_hash="h2",
            ),
            Profile(
                user_id=u3.id,
                summary="C用户画像：追求刺激，节奏很快。",
                embedding=_emb([-1.0, 0.0]),
                source_hash="h3",
            ),
        ]
    )
    session.commit()

    client = FakeRerankClient()
    r1 = match_user(user_id=u1.id, session=session, client=client, recall_k=50)
    assert client.calls == 1
    assert r1["user_id"] == u2.id
    assert 0.0 <= r1["score"] <= 1.0
    assert isinstance(r1["reasons"], list)

    # Second call should be cache hit (no LLM rerank).
    r2 = match_user(user_id=u1.id, session=session, client=client, recall_k=50)
    assert client.calls == 1
    assert r2["user_id"] == u2.id
    assert r2["score"] == r1["score"]


def test_match_agent_cache_invalidates_on_profile_change(session: Session) -> None:
    u1 = User(consent=True)
    u2 = User(consent=True)
    session.add_all([u1, u2])
    session.flush()

    p1 = Profile(user_id=u1.id, summary="A画像", embedding=_emb([1.0, 0.0]), source_hash="h1")
    p2 = Profile(user_id=u2.id, summary="B画像", embedding=_emb([1.0, 0.0]), source_hash="h2")
    session.add_all([p1, p2])
    session.commit()

    client = FakeRerankClient()
    match_user(user_id=u1.id, session=session, client=client)
    assert client.calls == 1

    # Change candidate profile hash -> should require rerank again.
    p2.source_hash = "h2_changed"
    session.commit()

    match_user(user_id=u1.id, session=session, client=client)
    assert client.calls == 2


def test_match_agent_requires_consent(session: Session) -> None:
    user = User(consent=False)
    other = User(consent=True)
    session.add_all([user, other])
    session.flush()
    session.add_all(
        [
            Profile(user_id=user.id, summary="X", embedding=_emb([1.0, 0.0]), source_hash="x"),
            Profile(user_id=other.id, summary="Y", embedding=_emb([1.0, 0.0]), source_hash="y"),
        ]
    )
    session.commit()

    with pytest.raises(PermissionError):
        match_user(user_id=user.id, session=session, client=FakeRerankClient())

