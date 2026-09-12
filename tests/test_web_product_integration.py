import os
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEMP_DIR = tempfile.TemporaryDirectory()
_DB_PATH = Path(_TEMP_DIR.name) / "tongpin-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["AUTO_CREATE_DB"] = "true"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["COOKIE_SECURE"] = "false"
os.environ["REALTIME_BROKER_ENABLED"] = "false"

from app.api.websocket import _origin_allowed  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.seed import BASE_ANSWERS  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    _TEMP_DIR.cleanup()


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("tongpin_csrf")}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "测试用户",
            "email": email,
            "password": "correct-horse-battery-staple",
            "birth_year": 1994,
            "region": "上海",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str = "correct-horse-battery-staple") -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _grant_all(client: TestClient) -> None:
    for scope in ("matching:v1", "conversation:v1", "outcomes:v1"):
        response = client.post(
            "/api/v1/consents",
            json={"scope": scope, "purpose": f"用于测试 {scope} 范围内的核心流程"},
            headers=_csrf(client),
        )
        assert response.status_code == 200, response.text


def test_health_and_security_headers(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["model_version"] == "rules-v0.1"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_complete_product_flow_without_internal_scores(client: TestClient):
    user = _register(client, "flow@example.com")
    assert user["user"]["display_name"] == "测试用户"

    denied = client.post("/api/v1/recommendations", headers=_csrf(client))
    assert denied.status_code == 403
    assert denied.json()["code"] == "CONSENT_REQUIRED"

    _grant_all(client)
    questionnaire = client.get("/api/v1/questionnaire")
    assert questionnaire.status_code == 200
    body = questionnaire.json()
    assert body["version"] == "relationship-signals-v0.1"
    assert 20 <= len(body["questions"]) <= 40

    submission = client.post(
        "/api/v1/questionnaire/submissions",
        json={"version": body["version"], "answers": deepcopy(BASE_ANSWERS)},
        headers={**_csrf(client), "Idempotency-Key": "questionnaire-1"},
    )
    assert submission.status_code == 200, submission.text
    assert len(submission.json()) == len(body["questions"])
    assert all(item["evidence_ids"] for item in submission.json())
    assert "confidence" not in submission.text
    assert "stability" not in submission.text

    generated = client.post(
        "/api/v1/recommendations",
        headers={
            **_csrf(client),
            "Idempotency-Key": "recommendation-1",
            "X-Session-Id": "session-1",
        },
    )
    assert generated.status_code == 200, generated.text
    recommendation = generated.json()
    assert recommendation["items"], "complete profile should receive candidates"
    serialized = str(recommendation)
    for forbidden in ("ranking_score", "success_probability", "confidence", "internal_score"):
        assert forbidden not in serialized
    first = recommendation["items"][0]
    assert first["common_signals"]
    assert first["differences"]
    assert first["unknowns"]
    assert first["how_to_continue"]

    detail = client.get(f"/api/v1/recommendations/{first['candidate_id']}")
    assert detail.status_code == 200, detail.text

    cues = client.get(f"/api/v1/recommendations/{first['candidate_id']}/cues")
    assert cues.status_code == 200, cues.text
    assert cues.json()
    assert "ranking_score" not in cues.text

    invitation = client.post(
        "/api/v1/connection-requests",
        json={
            "candidate_id": first["candidate_id"],
            "topic_text": cues.json()[0]["text"],
            "cue_type": cues.json()[0]["cue_type"],
            "personal_message": "想先从时间安排聊起。",
        },
        headers={**_csrf(client), "Idempotency-Key": "connection-request-1"},
    )
    assert invitation.status_code == 201, invitation.text
    connection_request = invitation.json()
    assert connection_request["status"] == "pending"
    assert connection_request["topic_text"] == cues.json()[0]["text"]

    with SessionLocal() as db:
        candidate = db.get(User, first["candidate_id"])
        assert candidate is not None
        candidate_email = candidate.email

    _login(client, candidate_email, "disabled-seed-account")
    incoming = client.get("/api/v1/connection-requests?direction=incoming&status=pending")
    assert incoming.status_code == 200
    assert [item["id"] for item in incoming.json()] == [connection_request["id"]]
    accepted = client.post(
        f"/api/v1/connection-requests/{connection_request['id']}/accept",
        headers={**_csrf(client), "Idempotency-Key": "connection-accept-1"},
    )
    assert accepted.status_code == 200, accepted.text
    conversation = accepted.json()
    assert conversation["status"] == "active"
    assert conversation["active_cue"]["text"] == cues.json()[0]["text"]

    _login(client, "flow@example.com")
    message = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"body": "你好，想先了解一下彼此对周末节奏的安排。", "client_message_id": "msg-1"},
        headers=_csrf(client),
    )
    assert message.status_code == 201, message.text
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert [item["body"] for item in messages.json()["items"]] == [message.json()["body"]]

    with client.websocket_connect(f"/api/v1/ws/conversations/{conversation['id']}") as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["type"] == "messages.snapshot"
        websocket.send_json(
            {
                "type": "message",
                "body": "也可以聊聊计划变化时怎样重新确认安排。",
                "client_message_id": "ws-message-1",
            }
        )
        created = websocket.receive_json()
        assert created["type"] == "message.created"
        assert created["data"]["body"] == "也可以聊聊计划变化时怎样重新确认安排。"

    outcome = client.post(
        "/api/v1/outcomes",
        json={
            "candidate_id": first["candidate_id"],
            "match_id": conversation["match_id"],
            "window_days": 14,
            "satisfaction": "positive",
            "continued_contact": True,
            "safety_event": False,
        },
        headers=_csrf(client),
    )
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["good_outcome"] is True


def test_high_risk_safety_event_vetoes_candidate(client: TestClient):
    _register(client, "safety@example.com")
    _grant_all(client)
    questionnaire = client.get("/api/v1/questionnaire").json()
    submitted = client.post(
        "/api/v1/questionnaire/submissions",
        json={"version": questionnaire["version"], "answers": deepcopy(BASE_ANSWERS)},
        headers=_csrf(client),
    )
    assert submitted.status_code == 200

    generated = client.post(
        "/api/v1/recommendations",
        headers={
            **_csrf(client),
            "Idempotency-Key": "safety-recommendation-1",
            "X-Session-Id": "safety-session-1",
        },
    ).json()
    candidate_id = generated["items"][0]["candidate_id"]
    report = client.post(
        "/api/v1/safety/reports",
        json={
            "subject_id": candidate_id,
            "event_type": "boundary_violation",
            "severity": "high",
            "details": "测试边界事件，正文不进入数据库。",
        },
        headers=_csrf(client),
    )
    assert report.status_code == 201, report.text

    regenerated = client.post(
        "/api/v1/recommendations",
        headers={
            **_csrf(client),
            "Idempotency-Key": "safety-recommendation-2",
            "X-Session-Id": "safety-session-2",
        },
    )
    assert regenerated.status_code == 200, regenerated.text
    assert candidate_id not in {item["candidate_id"] for item in regenerated.json()["items"]}


def test_csrf_and_consent_privacy_are_enforced(client: TestClient):
    _register(client, "privacy@example.com")
    response = client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于验证请求保护"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"

    granted = client.post(
        "/api/v1/consents",
        json={"scope": "matching:v1", "purpose": "用于验证撤回后的匹配阻断"},
        headers=_csrf(client),
    )
    assert granted.status_code == 200
    revoked = client.delete("/api/v1/consents/matching:v1", headers=_csrf(client))
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None


def test_deletion_removes_claims_and_revokes_session(client: TestClient):
    _register(client, "delete@example.com")
    _grant_all(client)
    questionnaire = client.get("/api/v1/questionnaire").json()
    submitted = client.post(
        "/api/v1/questionnaire/submissions",
        json={"version": questionnaire["version"], "answers": deepcopy(BASE_ANSWERS)},
        headers=_csrf(client),
    )
    assert submitted.status_code == 200
    assert client.get("/api/v1/claims").json()

    deletion = client.request(
        "DELETE",
        "/api/v1/privacy/me",
        headers=_csrf(client),
    )
    assert deletion.status_code == 202, deletion.text
    assert deletion.json()["status"] == "completed"
    after = client.get("/api/v1/auth/me")
    assert after.status_code == 401


def test_codespaces_websocket_origin_is_allowed_only_in_development():
    assert _origin_allowed("https://example-3000.app.github.dev")
    assert not _origin_allowed("https://example.invalid")



def _prepare_seed_conversation(
    client: TestClient,
    email: str,
    prefix: str,
) -> tuple[str, dict]:
    _register(client, email)
    _grant_all(client)
    questionnaire = client.get("/api/v1/questionnaire").json()
    submitted = client.post(
        "/api/v1/questionnaire/submissions",
        json={"version": questionnaire["version"], "answers": deepcopy(BASE_ANSWERS)},
        headers=_csrf(client),
    )
    assert submitted.status_code == 200, submitted.text
    recommendations = client.post(
        "/api/v1/recommendations",
        headers={
            **_csrf(client),
            "Idempotency-Key": f"{prefix}-recommendation",
            "X-Session-Id": f"{prefix}-session",
        },
    ).json()
    with SessionLocal() as db:
        candidate = next(
            db.get(User, item["candidate_id"])
            for item in recommendations["items"]
            if db.get(User, item["candidate_id"]).is_seed
        )
    assert candidate is not None
    cues = client.get(f"/api/v1/recommendations/{candidate.id}/cues").json()
    request_response = client.post(
        "/api/v1/connection-requests",
        json={
            "candidate_id": candidate.id,
            "topic_text": cues[0]["text"],
            "cue_type": cues[0]["cue_type"],
            "personal_message": "希望从具体情境开始认识。",
        },
        headers={**_csrf(client), "Idempotency-Key": f"{prefix}-request"},
    )
    assert request_response.status_code == 201, request_response.text
    request = request_response.json()
    _login(client, candidate.email, "disabled-seed-account")
    accepted = client.post(
        f"/api/v1/connection-requests/{request['id']}/accept",
        headers={**_csrf(client), "Idempotency-Key": f"{prefix}-accept"},
    )
    assert accepted.status_code == 200, accepted.text
    _login(client, email)
    return candidate.id, accepted.json()

def test_block_stops_conversation_and_report_can_reference_message(client: TestClient):
    candidate_id, conversation = _prepare_seed_conversation(client, "block@example.com", "block")
    sent = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"body": "这是一条用于安全测试的消息。", "client_message_id": "block-message-1"},
        headers=_csrf(client),
    )
    assert sent.status_code == 201, sent.text
    report = client.post(
        "/api/v1/safety/reports",
        json={
            "subject_id": candidate_id,
            "conversation_id": conversation["id"],
            "message_id": sent.json()["id"],
            "event_type": "boundary_violation",
            "severity": "high",
            "details": "测试举报引用，不写入普通日志。",
        },
        headers=_csrf(client),
    )
    assert report.status_code == 201, report.text
    assert report.json()["conversation_id"] == conversation["id"]
    assert report.json()["message_id"] == sent.json()["id"]

    blocked = client.post(
        "/api/v1/blocks",
        json={"blocked_user_id": candidate_id, "reason_private": "停止联系"},
        headers=_csrf(client),
    )
    assert blocked.status_code == 201, blocked.text
    rejected = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"body": "这条不应发送。", "client_message_id": "block-message-2"},
        headers=_csrf(client),
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "CONVERSATION_CLOSED"

def test_conversation_consent_revocation_blocks_future_messages(client: TestClient):
    _candidate_id, conversation = _prepare_seed_conversation(
        client, "consent-chat@example.com", "consent-chat"
    )
    revoked = client.delete("/api/v1/consents/conversation:v1", headers=_csrf(client))
    assert revoked.status_code == 200, revoked.text
    rejected = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"body": "撤回授权后不应发送。", "client_message_id": "consent-revoked-message"},
        headers=_csrf(client),
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "CONVERSATION_CLOSED"


def test_decline_enforces_cooldown_for_repeated_requests(client: TestClient):
    _register(client, "decline-owner@example.com")
    _grant_all(client)
    questionnaire = client.get("/api/v1/questionnaire").json()
    client.post(
        "/api/v1/questionnaire/submissions",
        json={"version": questionnaire["version"], "answers": deepcopy(BASE_ANSWERS)},
        headers=_csrf(client),
    )
    recommendations = client.post(
        "/api/v1/recommendations",
        headers={**_csrf(client), "Idempotency-Key": "decline-recommendation"},
    ).json()
    with SessionLocal() as db:
        candidate = next(
            db.get(User, item["candidate_id"])
            for item in recommendations["items"]
            if db.get(User, item["candidate_id"]).is_seed
        )
    first = client.post(
        "/api/v1/connection-requests",
        json={"candidate_id": candidate.id, "topic_text": "先确认一个具体情境。"},
        headers={**_csrf(client), "Idempotency-Key": "decline-request-1"},
    )
    assert first.status_code == 201, first.text
    _login(client, candidate.email, "disabled-seed-account")
    declined = client.post(
        f"/api/v1/connection-requests/{first.json()['id']}/decline",
        json={"reason_private": "暂不合适"},
        headers=_csrf(client),
    )
    assert declined.status_code == 200, declined.text
    _login(client, "decline-owner@example.com")
    repeated = client.post(
        "/api/v1/connection-requests",
        json={"candidate_id": candidate.id, "topic_text": "再次尝试。"},
        headers={**_csrf(client), "Idempotency-Key": "decline-request-2"},
    )
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "CONNECTION_REQUEST_COOLDOWN"
