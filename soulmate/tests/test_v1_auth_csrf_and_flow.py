from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


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
    body = resp.json()
    assert "user" in body and "csrf_token" in body
    assert client.cookies.get("tongpin_session")
    assert client.cookies.get("tongpin_csrf")
    assert body["csrf_token"] == client.cookies.get("tongpin_csrf")
    return body


def _login(client: TestClient, *, email: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert client.cookies.get("tongpin_session")
    assert client.cookies.get("tongpin_csrf")
    assert body["csrf_token"] == client.cookies.get("tongpin_csrf")
    return body


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("tongpin_csrf")
    assert token
    return {"X-CSRF-Token": token}


def _capture_cookies(client: TestClient) -> dict[str, str]:
    return {k: v for k, v in client.cookies.items()}


def _restore_cookies(client: TestClient, jar: dict[str, str]) -> None:
    client.cookies.clear()
    client.cookies.update(jar)


def test_v1_auth_register_login_me_logout_csrf(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    body = _register(client, email=email, password=password)
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "user"
    assert body["user"]["status"] == "active"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 403
    assert logout.json()["code"] == "CSRF_INVALID"

    logout = client.post("/api/v1/auth/logout", headers=_csrf_headers(client))
    assert logout.status_code == 200

    me2 = client.get("/api/v1/auth/me")
    assert me2.status_code == 401
    assert me2.json()["code"] == "UNAUTHORIZED"

    client.cookies.clear()
    _login(client, email=email, password=password)
    me3 = client.get("/api/v1/auth/me")
    assert me3.status_code == 200


def test_v1_csrf_required_for_post(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"
    _register(client, email=email, password=password)

    resp = client.post("/api/v1/consents", json={"scope": "matching:v1", "purpose": "用于关系匹配"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "CSRF_INVALID"

    ok = client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于关系匹配"},
        headers=_csrf_headers(client),
    )
    assert ok.status_code == 200, ok.text


def test_v1_questionnaire_claims_recommendations_space_state(client: TestClient) -> None:
    email1 = f"user-{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    _register(client, email=email1, password=password)
    state0 = client.get("/api/v1/space/state")
    assert state0.status_code == 200
    assert state0.json()["state"] == "EXPLORING"

    client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于关系匹配"},
        headers=_csrf_headers(client),
    )

    q = client.get("/api/v1/questionnaire")
    assert q.status_code == 200
    assert q.json()["version"] == "relationship-signals-v0.1"

    sub = client.post(
        "/api/v1/questionnaire/submissions",
        json={
            "version": "relationship-signals-v0.1",
            "answers": {"life_weekend": "stay_home", "comm_reply_frequency": "daily"},
        },
        headers=_csrf_headers(client),
    )
    assert sub.status_code == 200, sub.text
    claims = sub.json()
    assert isinstance(claims, list) and claims

    state1 = client.get("/api/v1/space/state")
    assert state1.status_code == 200
    assert state1.json()["state"] == "SELF_PROFILE_READY"
    assert state1.json()["can_match"] is True

    # Create another real user (candidate) with matching consent + claims.
    cookies_u1 = _capture_cookies(client)
    client.cookies.clear()
    _register(client, email=email2, password=password, display_name="林屿")
    client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于关系匹配"},
        headers=_csrf_headers(client),
    )
    client.post(
        "/api/v1/questionnaire/submissions",
        json={
            "version": "relationship-signals-v0.1",
            "answers": {"life_weekend": "stay_home", "comm_reply_frequency": "few_times_week"},
        },
        headers=_csrf_headers(client),
    )

    # Back to user1: generate recommendations, should include user2.
    _restore_cookies(client, cookies_u1)
    recos = client.post("/api/v1/recommendations", headers=_csrf_headers(client))
    assert recos.status_code == 200, recos.text
    body = recos.json()
    assert "items" in body and body["items"]
    assert all("ranking_score" not in item for item in body["items"])

    state2 = client.get("/api/v1/space/state")
    assert state2.status_code == 200
    assert state2.json()["state"] in {"MATCHING", "SELF_PROFILE_READY"}


def test_v1_invitations_matches_messages_ws(client: TestClient) -> None:
    email1 = f"user-{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    u1 = _register(client, email=email1, password=password, display_name="甲")
    user1_id = u1["user"]["id"]
    client.post(
        "/api/v1/consents",
        json={"scope": "conversation:v1", "purpose": "用于聊天"},
        headers=_csrf_headers(client),
    )
    cookies_u1 = _capture_cookies(client)

    client.cookies.clear()
    u2 = _register(client, email=email2, password=password, display_name="乙")
    user2_id = u2["user"]["id"]
    client.post(
        "/api/v1/consents",
        json={"scope": "conversation:v1", "purpose": "用于聊天"},
        headers=_csrf_headers(client),
    )
    _capture_cookies(client)

    # Invite u2 -> u1 (pending)
    inv = client.post(
        "/api/v1/invitations",
        json={"candidate_id": user1_id, "message": "想从一个具体场景开始了解。"},
        headers=_csrf_headers(client),
    )
    assert inv.status_code == 200, inv.text
    assert inv.json()["status"] == "pending"
    match_id = inv.json()["match_id"]

    # u2 cannot send messages while pending
    deny = client.post(
        f"/api/v1/matches/{match_id}/messages",
        json={"body": "hi", "client_message_id": "c1"},
        headers=_csrf_headers(client),
    )
    assert deny.status_code == 403
    assert deny.json()["code"] == "MATCH_NOT_CONNECTED"

    # u1 invites back -> connected
    _restore_cookies(client, cookies_u1)
    inv2 = client.post(
        "/api/v1/invitations",
        json={"candidate_id": user2_id, "message": "想从一个具体场景开始了解。"},
        headers=_csrf_headers(client),
    )
    assert inv2.status_code == 200, inv2.text
    assert inv2.json()["status"] == "connected"

    matches = client.get("/api/v1/matches")
    assert matches.status_code == 200
    assert any(m["status"] == "connected" for m in matches.json())

    msg = client.post(
        f"/api/v1/matches/{match_id}/messages",
        json={"body": "最近有什么小事让你觉得生活变好了？", "client_message_id": "uuid-1"},
        headers=_csrf_headers(client),
    )
    assert msg.status_code == 200, msg.text
    first_id = msg.json()["id"]

    # idempotent
    msg2 = client.post(
        f"/api/v1/matches/{match_id}/messages",
        json={"body": "最近有什么小事让你觉得生活变好了？", "client_message_id": "uuid-1"},
        headers=_csrf_headers(client),
    )
    assert msg2.status_code == 200
    assert msg2.json()["id"] == first_id

    with client.websocket_connect(f"/api/v1/ws/matches/{match_id}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "messages.snapshot"
