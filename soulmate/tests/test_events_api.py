from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.events import POST_EVENTS_LIMIT
from app.core.ratelimit import RateLimiter
from app.models import BehaviorEventType, User


def test_post_events_and_get_events(client: TestClient, api_session: Session) -> None:
    user = User(consent=True)
    api_session.add(user)
    api_session.commit()

    payload = {
        "events": [
            {
                "user_id": user.id,
                "event_type": BehaviorEventType.BROWSE.value,
                "target_id": "card:1",
                "duration_ms": 1200,
            },
            {
                "user_id": user.id,
                "event_type": BehaviorEventType.DWELL.value,
                "target_id": "profile:42",
                "duration_ms": 9000,
            },
        ]
    }
    resp = client.post("/events", json=payload)
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 2

    resp2 = client.get(f"/users/{user.id}/events?limit=10")
    assert resp2.status_code == 200
    items = resp2.json()["items"]
    assert len(items) == 2
    assert {item["event_type"] for item in items} == {"browse", "dwell"}


def test_post_events_missing_user(client: TestClient) -> None:
    resp = client.post(
        "/events",
        json={
            "events": [
                {"user_id": 9999, "event_type": "browse", "target_id": "x", "duration_ms": 10}
            ]
        },
    )
    assert resp.status_code == 400
    assert "missing_user_ids" in resp.json()["detail"]


def test_post_events_requires_consent(client: TestClient, api_session: Session) -> None:
    user = User(consent=False)
    api_session.add(user)
    api_session.commit()

    resp = client.post(
        "/events",
        json={
            "events": [
                {
                    "user_id": user.id,
                    "event_type": "browse",
                    "target_id": "x",
                    "duration_ms": 10,
                }
            ]
        },
    )
    assert resp.status_code == 403


def test_post_events_rate_limited(client: TestClient, api_session: Session) -> None:
    user = User(consent=True)
    api_session.add(user)
    api_session.commit()

    limiter = RateLimiter()
    key = "/events:testclient"
    for _ in range(POST_EVENTS_LIMIT.limit):
        assert limiter.allow(key=key, rule=POST_EVENTS_LIMIT) is True
    client.app.state.rate_limiter = limiter

    resp = client.post(
        "/events",
        json={
            "events": [
                {"user_id": user.id, "event_type": "browse", "target_id": "x", "duration_ms": 10}
            ]
        },
    )
    assert resp.status_code == 429


def test_post_events_validation(client: TestClient) -> None:
    resp = client.post(
        "/events",
        json={"events": [{"user_id": 0, "event_type": "nope", "target_id": "x", "duration_ms": -1}]},
    )
    assert resp.status_code == 422


def test_get_events_validation(client: TestClient) -> None:
    resp = client.get("/users/0/events?limit=9999")
    assert resp.status_code == 422
