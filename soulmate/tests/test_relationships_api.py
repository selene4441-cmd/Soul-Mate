from __future__ import annotations

import pytest

from app.models import User


def seed_user(session, *, consent: bool = True) -> User:
    user = User(consent=consent)
    session.add(user)
    session.commit()
    return user


def test_post_relationship_signal_requires_consent(client, api_session) -> None:
    a = seed_user(api_session, consent=True)
    b = seed_user(api_session, consent=False)

    resp = client.post(
        f"/relationships/{a.id}/{b.id}/signals",
        json={"kind": "shared_topic", "content": "都聊到了同一个话题", "weight": 1.0},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert "no_consent_user_ids" in body["detail"]


def test_post_relationship_signal_rate_limited(client, api_session) -> None:
    a = seed_user(api_session, consent=True)
    b = seed_user(api_session, consent=True)

    for _ in range(3):
        ok = client.post(
            f"/relationships/{a.id}/{b.id}/signals",
            json={"kind": "shared_topic", "content": "聊到了共同话题", "weight": 1.0},
        )
        assert ok.status_code == 200
        payload = ok.json()
        assert payload["alpha"] > 0
        assert payload["beta"] > 0
        assert 0.0 <= payload["mean"] <= 1.0
        assert payload["entropy"] >= 0.0

    limited = client.post(
        f"/relationships/{a.id}/{b.id}/signals",
        json={"kind": "shared_topic", "content": "继续刷信号", "weight": 1.0},
    )
    assert limited.status_code == 429
    assert limited.json()["detail"] == "rate_limited"


@pytest.mark.parametrize(
    "kind",
    ["message_tone", "response_latency", "shared_topic", "conflict", "repair"],
)
def test_post_relationship_signal_accepts_allowed_kinds(client, api_session, kind: str) -> None:
    a = seed_user(api_session, consent=True)
    b = seed_user(api_session, consent=True)

    resp = client.post(
        f"/relationships/{a.id}/{b.id}/signals",
        json={"kind": kind, "content": "ok", "weight": 1.0},
    )
    assert resp.status_code == 200

