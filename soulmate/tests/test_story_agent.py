from __future__ import annotations

import pytest

from app.models import Elicitation, ElicitationKind, Profile, Response, User


def seed_user(session, *, consent: bool = True) -> User:
    user = User(consent=consent)
    session.add(user)
    session.commit()
    return user


def seed_profile(session, user_id: int, *, summary: str = "我会在意被认真对待") -> Profile:
    profile = Profile(user_id=user_id, summary=summary, embedding=b"\x00\x00\x00\x00", source_hash="h")
    session.add(profile)
    session.commit()
    return profile


def seed_confirm_responses(session, user_id: int, *, count: int) -> None:
    elicitation = Elicitation(
        question="你更在意被认真对待吗？",
        options=[
            {"text": "同意", "polarity": "confirm"},
            {"text": "不同意", "polarity": "disconfirm"},
            {"text": "不确定", "polarity": "uncertain"},
        ],
        kind=ElicitationKind.SINGLE_CHOICE,
    )
    session.add(elicitation)
    session.flush()

    session.add_all(
        [
            Response(user_id=user_id, elicitation_id=elicitation.id, choice="同意", reaction_time_ms=800)
            for _ in range(count)
        ]
    )
    session.commit()


def test_story_not_ready_returns_not_ready(client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id)

    resp = client.post(f"/users/{user.id}/story")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "not_ready"


@pytest.mark.parametrize(
    "banned",
    ["人格报告", "MBTI", "标签", "画像", "评分", "百分比"],
)
def test_story_ready_returns_story_and_blocks_banned_words(client, api_session, banned: str) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id, summary="我会在意被认真对待，也更喜欢用行动表达。")
    # PRIOR strength is 2 (alpha=1, beta=1); add 6 responses -> strength == 8.
    seed_confirm_responses(api_session, user.id, count=6)

    resp = client.post(f"/users/{user.id}/story")
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "我们好像已经有点了解你了"
    assert body["story"]
    assert len(body["story"]) <= 150
    assert "我" in body["story"]
    assert banned not in body["story"]

