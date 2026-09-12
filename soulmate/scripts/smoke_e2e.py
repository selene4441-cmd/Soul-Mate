"""用种子数据跑一遍前端要走的真实 HTTP 链路（TestClient，无需起服务）。

验证点对应 docs/api/API-CONTRACT.md 第 7 节 checklist 的关键几步。
用法::

    cd soulmate
    python -m scripts.seed_demo --reset     # 先造演示数据
    python -m scripts.smoke_e2e             # 或 python scripts/smoke_e2e.py

退出码 0 = 全部通过，1 = 有失败项。
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "password123"
OK, NG = "OK  ", "FAIL"
fails: list[str] = []


def check(label: str, cond: bool, extra: str = "") -> None:
    print(f"  [{OK if cond else NG}] {label}" + (f"  {extra}" if extra else ""))
    if not cond:
        fails.append(label)


def login(client: TestClient, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("tongpin_csrf")
    assert token
    return {"X-CSRF-Token": token}


with TestClient(app) as client:
    print("== 1. 登录与会话 ==")
    body = login(client, "demo1@example.com")
    check("登录返回 user + csrf_token", "user" in body and "csrf_token" in body)
    check("session/csrf cookie 都已下发", bool(client.cookies.get("tongpin_session")) and bool(client.cookies.get("tongpin_csrf")))
    me = client.get("/api/v1/auth/me")
    check("GET /auth/me 返回当前用户", me.status_code == 200 and me.json()["email"] == "demo1@example.com")

    print("== 2. CSRF 双提交 ==")
    bad = client.post("/api/v1/consents", json={"scope": "matching:v1", "purpose": "x"})
    check("不带 X-CSRF-Token 的 POST 被拒 403 CSRF_INVALID", bad.status_code == 403 and bad.json()["code"] == "CSRF_INVALID")
    good = client.post("/api/v1/consents", json={"scope": "matching:v1", "purpose": "x"}, headers=csrf(client))
    check("带 token 的 POST 通过", good.status_code == 200, str(good.json()))

    print("== 3. 状态机（四种 state 各账号各一种）==")
    expect = {
        "demo1@example.com": "MATCHING",
        "demo2@example.com": "CHAT",
        "demo3@example.com": "SELF_PROFILE_READY",
        "demo4@example.com": "EXPLORING",
    }
    jar = dict(client.cookies)
    for email, want in expect.items():
        client.cookies.clear()
        login(client, email)
        st = client.get("/api/v1/space/state").json()
        check(f"{email} → {want}", st["state"] == want, f"实际 {st['state']}")

    print("== 4. 推荐的理由与证据 ==")
    client.cookies.clear()
    login(client, "demo1@example.com")
    recos = client.post("/api/v1/recommendations", headers=csrf(client))
    check("POST /recommendations 200", recos.status_code == 200, recos.text[:80])
    payload = recos.json()
    items = payload.get("items", [])
    check("至少返回 1 条推荐", len(items) >= 1, f"{len(items)} 条")
    if items:
        first = items[0]
        check("每条都有非空 evidence_ids", all(it["evidence_ids"] for it in items), str([len(it["evidence_ids"]) for it in items]))
        check("headline 非空且不是硬编码常量", bool(first["headline"]) and "目前重视生活平衡" not in first["headline"], first["headline"])
        check("unknowns 字段存在且为数组", isinstance(first["unknowns"], list))
        flat = str(payload).lower()
        banned = [w for w in ("score", "percent", "rank", "level", "match_score", "similarity") if f'"{w}"' in flat]
        check("响应里没有分数/等级类字段", not banned, f"可疑字段 {banned}" if banned else "")

    print("== 5. 证据可溯源（evidence_ids 真能查到）==")
    import sqlalchemy as sa

    from app.core.db import get_engine
    from app.models import Evidence

    ev_ids = [e for it in items for e in it["evidence_ids"]]
    with sa.orm.Session(get_engine()) as s:
        found = s.execute(sa.select(Evidence.id).where(Evidence.id.in_(ev_ids))).scalars().all()
    check("所有 evidence_ids 都能在 evidences 表查到", len(found) == len(set(ev_ids)), f"{len(found)}/{len(set(ev_ids))}")

    print("== 6. 匹配与消息 ==")
    client.cookies.clear()
    login(client, "demo2@example.com")
    matches = client.get("/api/v1/matches").json()
    connected = [m for m in matches if m["status"] == "connected"]
    check("苏晚有一条 connected match", len(connected) == 1, str([ (m["match_id"], m["status"]) for m in matches ]))
    if connected:
        mid = connected[0]["match_id"]
        msgs = client.get(f"/api/v1/matches/{mid}/messages")
        check("能拉到历史消息", msgs.status_code == 200 and len(msgs.json()) >= 4, f"{len(msgs.json()) if msgs.status_code == 200 else msgs.status_code} 条")
        mid_ok = client.post(
            f"/api/v1/matches/{mid}/messages",
            json={"body": "联调测试消息", "client_message_id": "smoke-1"},
            headers=csrf(client),
        )
        check("发消息 200", mid_ok.status_code == 200, mid_ok.text[:80])
        again = client.post(
            f"/api/v1/matches/{mid}/messages",
            json={"body": "联调测试消息", "client_message_id": "smoke-1"},
            headers=csrf(client),
        )
        check("同 client_message_id 幂等返回同一条", again.status_code == 200 and again.json()["id"] == mid_ok.json()["id"])

        print("== 7. WebSocket ==")
        with client.websocket_connect(f"/api/v1/ws/matches/{mid}") as ws:
            snap = ws.receive_json()
            check("先收到 messages.snapshot", snap["type"] == "messages.snapshot", str(snap))
            first_evt = ws.receive_json()
            check("随后逐条回放 message.created", first_evt["type"] == "message.created", str(first_evt)[:100])

    print("== 8. 未鉴权访问 ==")
    client.cookies.clear()
    r = client.get("/api/v1/auth/me")
    check("无 cookie → 401 UNAUTHORIZED", r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED")

print()
print("结论:", "FAIL " + ", ".join(fails) if fails else "全部通过")
sys.exit(1 if fails else 0)
