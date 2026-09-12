"""WebSocket 鉴权与关闭码回归测试。

背景：``close(code)`` 若发生在 ``accept()`` 之前，uvicorn 会把握手拒掉并返回 HTTP 403，
浏览器只能看到 1006，无法区分「未登录」和「不属于该会话」。
契约（docs/api/API-CONTRACT.md §5.16）承诺的是 4401 / 4403，因此这里把行为钉住。
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

PASSWORD = "password123"


def _register(client: TestClient, *, display_name: str) -> dict:
    email = f"ws-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": display_name,
            "email": email,
            "password": PASSWORD,
            "birth_year": 1995,
            "region": "上海",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _consent(client: TestClient, scope: str) -> None:
    resp = client.post(
        "/api/v1/consents",
        json={"scope": scope, "purpose": "测试用途"},
        headers={"X-CSRF-Token": client.cookies.get("tongpin_csrf")},
    )
    assert resp.status_code == 200, resp.text


def _cookies(client: TestClient) -> dict[str, str]:
    return {k: v for k, v in client.cookies.items()}


def _connected_match(client: TestClient) -> str:
    """建两个用户并互相邀请，返回 connected 的 match_id。"""
    first = _register(client, display_name="甲")
    _consent(client, "conversation:v1")
    first_cookies = _cookies(client)
    client.cookies.clear()

    second = _register(client, display_name="乙")
    _consent(client, "conversation:v1")

    invite = client.post(
        "/api/v1/invitations",
        json={"candidate_id": first["user"]["id"], "message": "想从一个具体场景开始了解。"},
        headers={"X-CSRF-Token": client.cookies.get("tongpin_csrf")},
    )
    assert invite.status_code == 200, invite.text

    client.cookies.clear()
    client.cookies.update(first_cookies)
    back = client.post(
        "/api/v1/invitations",
        json={"candidate_id": second["user"]["id"], "message": "我也想问同一个问题。"},
        headers={"X-CSRF-Token": client.cookies.get("tongpin_csrf")},
    )
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "connected"
    return back.json()["match_id"]


def test_ws_rejects_without_session_cookie(client: TestClient) -> None:
    """未登录：应收到 4401 关闭码（而不是被降级成 403 / 1006）。"""
    match_id = _connected_match(client)
    client.cookies.clear()

    with client.websocket_connect(f"/api/v1/ws/matches/{match_id}") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()

    assert exc.value.code == 4401


def test_ws_rejects_non_member(client: TestClient) -> None:
    """已登录但不是这个会话的成员：应收到 4403。"""
    match_id = _connected_match(client)
    client.cookies.clear()
    _register(client, display_name="路人")

    with client.websocket_connect(f"/api/v1/ws/matches/{match_id}") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()

    assert exc.value.code == 4403


def test_ws_sends_snapshot_then_replays_messages(client: TestClient) -> None:
    """成员连接：先收到 messages.snapshot，再逐条回放历史消息。"""
    match_id = _connected_match(client)
    sent = client.post(
        f"/api/v1/matches/{match_id}/messages",
        json={"body": "最近有什么小事让你觉得生活变好了？", "client_message_id": "ws-1"},
        headers={"X-CSRF-Token": client.cookies.get("tongpin_csrf")},
    )
    assert sent.status_code == 200, sent.text

    with client.websocket_connect(f"/api/v1/ws/matches/{match_id}") as ws:
        snapshot = ws.receive_json()
        assert snapshot == {"type": "messages.snapshot", "data": []}

        first = ws.receive_json()
        assert first["type"] == "message.created"
        assert first["data"]["id"] == sent.json()["id"]
        assert first["data"]["body"] == "最近有什么小事让你觉得生活变好了？"
