"""推荐文案的可用性回归：面向用户的文本里不能出现内部维度键。

背景：``life_weekend`` / ``comm_reply_frequency`` 是问卷的 dimension 键，
直接出现在「共同点 / 差异」文案里，用户看到的是开发者字段名。
契约要求这些区块用中文说法（问卷的 section / 选项 label）。
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

PASSWORD = "password123"
RAW_DIMENSION_KEYS = ("life_weekend", "comm_reply_frequency")

ANSWERS = (
    {"life_weekend": "stay_home", "comm_reply_frequency": "daily"},
    {"life_weekend": "stay_home", "comm_reply_frequency": "few_times_week"},
)


def _register(client: TestClient, *, display_name: str) -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": display_name,
            "email": f"reco-{uuid.uuid4().hex[:8]}@example.com",
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


def _submit(client: TestClient, answers: dict[str, str]) -> None:
    version = client.get("/api/v1/questionnaire").json()["version"]
    resp = client.post(
        "/api/v1/questionnaire/submissions",
        json={"version": version, "answers": answers},
        headers={"X-CSRF-Token": client.cookies.get("tongpin_csrf")},
    )
    assert resp.status_code == 200, resp.text


def test_recommendation_text_uses_human_labels(client: TestClient) -> None:
    first = _register(client, display_name="甲")
    _consent(client, "matching:v1")
    _submit(client, ANSWERS[0])
    first_cookies = _cookies(client)

    client.cookies.clear()
    _register(client, display_name="乙")
    _consent(client, "matching:v1")
    _submit(client, ANSWERS[1])

    client.cookies.clear()
    client.cookies.update(first_cookies)
    resp = client.post(
        "/api/v1/recommendations",
        headers={"X-CSRF-Token": client.cookies.get("tongpin_csrf")},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["items"], "应至少返回一条推荐"

    # 只检查面向用户的文本字段，不检查 id / evidence_ids
    item = payload["items"][0]
    visible = json.dumps(
        {
            "headline": item["headline"],
            "common_signals": item["common_signals"],
            "differences": item["differences"],
            "unknowns": item["unknowns"],
            "how_to_continue": item["how_to_continue"],
        },
        ensure_ascii=False,
    )

    leaked = [key for key in RAW_DIMENSION_KEYS if key in visible]
    assert not leaked, f"面向用户的文案里不应出现内部维度键：{leaked}；实际文案：{visible}"

    # 「还不确定」区块是产品红线，必须始终有内容
    assert item["unknowns"], "「还不确定」区块不能为空"
    assert str(first["user"]["id"]) == str(item["candidate_id"]) or item["candidate_id"]
