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

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402
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

    invitation = client.post(
        "/api/v1/invitations",
        json={"candidate_id": first["candidate_id"], "message": "想先从时间安排聊起。"},
        headers={**_csrf(client), "Idempotency-Key": "invitation-1"},
    )
    assert invitation.status_code == 200, invitation.text
    match = invitation.json()
    assert match["status"] == "connected"

    message = client.post(
        f"/api/v1/matches/{match['id']}/messages",
        json={"body": "你好，想先了解一下彼此对周末节奏的安排。", "client_message_id": "msg-1"},
        headers=_csrf(client),
    )
    assert message.status_code == 201, message.text
    messages = client.get(f"/api/v1/matches/{match['id']}/messages")
    assert [item["body"] for item in messages.json()] == [message.json()["body"]]

    with client.websocket_connect(f"/api/v1/ws/matches/{match['id']}") as websocket:
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
            "match_id": match["id"],
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
