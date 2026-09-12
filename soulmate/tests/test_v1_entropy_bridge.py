from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.belief_store import load_posterior
from app.models import Evidence


def _register(client: TestClient, *, email: str, password: str, display_name: str = "用户昵称") -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": display_name,
            "email": email,
            "password": password,
            "birth_year": 1994,
            "region": "上海",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("tongpin_csrf")
    assert token
    return {"X-CSRF-Token": token}


def _capture_cookies(client: TestClient) -> dict[str, str]:
    return {k: v for k, v in client.cookies.items()}


def _restore_cookies(client: TestClient, jar: dict[str, str]) -> None:
    client.cookies.clear()
    client.cookies.update(jar)


def _all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys |= set(obj.keys())
        for v in obj.values():
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _all_keys(item)
    return keys


def test_v1_entropy_bridge_and_recommendation_evidence(client: TestClient, api_engine) -> None:
    password = "password123"
    email1 = f"user-{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"user-{uuid.uuid4().hex[:8]}@example.com"

    u1 = _register(client, email=email1, password=password, display_name="甲")
    user1_id = int(u1["user"]["id"])
    client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于关系匹配"},
        headers=_csrf_headers(client),
    )
    client.post(
        "/api/v1/questionnaire/submissions",
        json={
            "version": "relationship-signals-v0.1",
            "answers": {"life_weekend": "stay_home", "comm_reply_frequency": "daily"},
        },
        headers=_csrf_headers(client),
    )

    with Session(api_engine) as session:
        posterior = load_posterior(session, user_id=user1_id)
        assert (posterior.alpha, posterior.beta) != (1.0, 1.0)

    cookies_u1 = _capture_cookies(client)
    client.cookies.clear()

    u2 = _register(client, email=email2, password=password, display_name="林屿")
    user2_id = int(u2["user"]["id"])
    client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于关系匹配"},
        headers=_csrf_headers(client),
    )
    client.post(
        "/api/v1/questionnaire/submissions",
        json={
            "version": "relationship-signals-v0.1",
            "answers": {"life_weekend": "go_out", "comm_reply_frequency": "few_times_week"},
        },
        headers=_csrf_headers(client),
    )

    _restore_cookies(client, cookies_u1)
    recos = client.post("/api/v1/recommendations", headers=_csrf_headers(client))
    assert recos.status_code == 200, recos.text
    body = recos.json()
    assert body["items"]

    forbidden_keys = {"score", "percent", "rank", "label", "level"}
    assert not (_all_keys(body) & forbidden_keys)

    with Session(api_engine) as session:
        for item in body["items"]:
            assert item["candidate_id"] == str(user2_id)
            assert item["evidence_ids"], "recommendation evidence_ids must be non-empty"
            for evidence_id in item["evidence_ids"]:
                assert session.get(Evidence, evidence_id) is not None

