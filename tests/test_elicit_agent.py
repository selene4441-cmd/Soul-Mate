from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.agents.elicit_agent import (
    apply_guess_response,
    expected_information_gain,
    generate_guess_cards,
)
from app.core.belief import BetaPosterior, entropy
from app.models import Belief, Profile, User


@dataclass
class FakeElicitClient:
    chat_model: str = "gpt-5.2"
    calls: int = 0

    def generate_cards(self, *, user_profile: str, belief_p: float):
        self.calls += 1
        cards: list[dict[str, Any]] = [
            {
                "question": "我猜：你其实更怕被误解。",
                "options": [
                    {"text": "是，点赞=站队/背书，所以很克制", "polarity": "confirm"},
                    {"text": "不是，我表达很直接", "polarity": "disconfirm"},
                    {"text": "跳过（不想回答）", "polarity": "uncertain"},
                ],
                "evidence_weight": 1,
            },
            {
                "question": "我猜：你会先观察再投入。",
                "options": [
                    {"text": "同意：先看行动再给心", "polarity": "confirm"},
                    {"text": "不同意：我会先热情投入", "polarity": "disconfirm"},
                    {"text": "不确定：看情况", "polarity": "uncertain"},
                ],
                "evidence_weight": 2,
            },
            {
                "question": "我猜：你对边界很敏感。",
                "options": [
                    {"text": "同意", "polarity": "confirm"},
                    {"text": "不同意", "polarity": "disconfirm"},
                    {"text": "不确定", "polarity": "uncertain"},
                ],
                "evidence_weight": 3,
            },
        ]
        return cards, {"total_tokens": 1}


def test_expected_information_gain_zero_at_extremes() -> None:
    assert expected_information_gain(BetaPosterior(alpha=1e9, beta=1.0)) < 1e-6
    assert expected_information_gain(BetaPosterior(alpha=1.0, beta=1e9)) < 1e-6


def test_expected_information_gain_increases_with_weight() -> None:
    p = BetaPosterior(alpha=1.0, beta=1.0)
    ig1 = expected_information_gain(p, evidence_weight=1.0)
    ig2 = expected_information_gain(p, evidence_weight=2.0)
    ig3 = expected_information_gain(p, evidence_weight=3.0)
    assert ig1 > 0
    assert ig1 < ig2 < ig3


def test_generate_guess_cards_creates_three_elicitations(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.flush()
    session.add(Profile(user_id=user.id, summary="画像摘要", embedding=b"\x00\x00\x80?"))
    session.commit()

    client = FakeElicitClient()
    cards = generate_guess_cards(user_id=user.id, posterior=BetaPosterior(1.0, 1.0), session=session, client=client)
    assert client.calls == 1
    assert len(cards) == 3
    assert all(c.elicitation_id > 0 for c in cards)
    assert all(c.expected_information_gain >= 0.0 for c in cards)


def test_apply_guess_response_updates_belief_and_profile(session: Session) -> None:
    user = User(consent=True)
    session.add(user)
    session.flush()
    session.add(Profile(user_id=user.id, summary="原始画像", embedding=b"\x00\x00\x80?"))
    session.commit()

    cards = generate_guess_cards(
        user_id=user.id,
        posterior=BetaPosterior(1.0, 1.0),
        session=session,
        client=FakeElicitClient(),
    )
    posterior = BetaPosterior(1.0, 1.0)
    entropy_before = entropy(posterior.mean)
    new_posterior = apply_guess_response(
        user_id=user.id,
        elicitation_id=cards[0].elicitation_id,
        posterior=posterior,
        choice="是，点赞=站队/背书，所以很克制",
        reaction_time_ms=123,
        session=session,
        hypothesis="match:test",
        evidence_weight=cards[0].evidence_weight,
    )
    assert new_posterior.mean > posterior.mean
    assert entropy(new_posterior.mean) < entropy_before

    belief = session.execute(
        sa.select(Belief).where(Belief.user_id == user.id, Belief.hypothesis == "match:test")
    ).scalar_one()
    assert 0.0 <= belief.confidence <= 1.0
    assert belief.confidence != 0.5

    profile = session.get(Profile, user.id)
    assert profile is not None
    assert "猜测卡反馈" in profile.summary
