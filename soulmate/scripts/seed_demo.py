"""生成前端联调用的演示数据（v1 链路）。

为什么需要它：`gen_synthetic.py` 造的是旧 agent 链路（Profile/embedding/猜测卡）的数据，
它创建的 `User(consent=True)` **没有 email / password**，无法用 `/api/v1/auth/login` 登录。
前端要跑通 v1 全流程（注册 → 授权 → 问卷 → 推荐 → 邀请 → 聊天），需要一份能登录、
且四个账号分别停在四种 `space/state` 上的种子数据。

本脚本刻意**复用真实接口函数**（不是手写 SQL），保证种子数据与线上代码路径一致。

用法::

    cd soulmate
    python -m alembic upgrade head          # 首次需要建表
    python -m scripts.seed_demo             # 或 python scripts/seed_demo.py
    python -m scripts.seed_demo --reset     # 先删掉演示账号再重建

跑完后每个账号的密码都是 `password123`；四个主账号分别停在
EXPLORING / SELF_PROFILE_READY / MATCHING / CHAT 四种 `space/state` 上。
"""

from __future__ import annotations

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import Response as HTTPResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import RegisterIn, register
from app.api.v1.consents import ConsentIn, post_consent
from app.api.v1.invitations import InvitationIn, create_invitation
from app.api.v1.questionnaire import QuestionnaireSubmissionIn, submit_questionnaire
from app.api.v1.questionnaire_def import QUESTIONNAIRE, QUESTIONNAIRE_VERSION
from app.api.v1.recommendations import create_recommendations
from app.api.v1.space import get_space_state
from app.core.db import get_engine
from app.models import (
    Claim,
    Consent,
    Evidence,
    Invitation,
    Match,
    MatchMessage,
    RecommendationItem,
    RecommendationSession,
    Response,
    SessionToken,
    User,
)

PASSWORD = "password123"

# 四个账号分别停在四种 space/state，前端切账号就能看到四种界面
PERSONAS = [
    {
        "email": "demo1@example.com",
        "display_name": "林屿",
        "birth_year": 1994,
        "region": "上海",
        "answers": {"life_weekend": "stay_home", "comm_reply_frequency": "daily"},
        "intent": "MATCHING（已答 + 已生成推荐 + 有一条待回应邀请）",
    },
    {
        "email": "demo2@example.com",
        "display_name": "苏晚",
        "birth_year": 1996,
        "region": "杭州",
        "answers": {"life_weekend": "stay_home", "comm_reply_frequency": "few_times_week"},
        "intent": "CHAT（已答 + 与「周聿」已 connected + 有聊天记录）",
    },
    {
        "email": "demo3@example.com",
        "display_name": "周聿",
        "birth_year": 1993,
        "region": "北京",
        "answers": {"life_weekend": "go_out", "comm_reply_frequency": "daily"},
        "intent": "SELF_PROFILE_READY（已授权已答题，但还没生成过推荐）",
    },
    {
        "email": "demo4@example.com",
        "display_name": "何枝",
        "birth_year": 1999,
        "region": "成都",
        "answers": {},  # 故意不答题
        "intent": "EXPLORING（还没有授权话题相关的必答数据）",
    },
]

CHAT_LINES = [
    (0, "最近有什么小事让你觉得生活变好了？"),
    (1, "大概是周末早起去菜市场，买完菜顺手买了束花。"),
    (0, "这个我懂。我最近开始认真做饭，切菜那二十分钟特别安静。"),
    (1, "那你周末一般会留多久给自己？"),
]

# 状态机里 CHAT 优先级最高：只要进了 connected match，无论有没有答题都会是 CHAT。
# 所以「聊天演示」需要一个配套账号，否则会把上面四个主账号的状态搅乱。
CHAT_PARTNER = {
    "email": "demo5@example.com",
    "display_name": "温野",
    "birth_year": 1992,
    "region": "深圳",
    "intent": "配套账号：只用来和「苏晚」形成 CHAT 演示（不答题）",
}


def _get_or_create_user(session, *, email: str, display_name: str, birth_year: int, region: str) -> User:
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is not None:
        return user
    auth = register(
        payload=RegisterIn(
            display_name=display_name,
            email=email,
            password=PASSWORD,
            birth_year=birth_year,
            region=region,
        ),
        response=HTTPResponse(),
        db=session,
    )
    return session.get(User, int(auth.user.id))


def _reset(session) -> None:
    emails = [p["email"] for p in PERSONAS] + [CHAT_PARTNER["email"]]
    users = session.execute(select(User).where(User.email.in_(emails))).scalars().all()
    if not users:
        print("  （没有需要清理的演示账号）")
        return
    ids = [int(u.id) for u in users]

    pairs = (
        session.execute(
            select(Match.id).where(Match.user_a_id.in_(ids) | Match.user_b_id.in_(ids))
        )
        .scalars()
        .all()
    )
    if pairs:
        session.query(MatchMessage).filter(MatchMessage.match_id.in_(pairs)).delete(
            synchronize_session=False
        )
    session.query(Match).filter(Match.user_a_id.in_(ids) | Match.user_b_id.in_(ids)).delete(
        synchronize_session=False
    )
    for model, column in (
        (Invitation, Invitation.from_user_id),
        (Invitation, Invitation.to_user_id),
        (RecommendationItem, RecommendationItem.user_id),
        (RecommendationSession, RecommendationSession.user_id),
    ):
        session.query(model).filter(column.in_(ids)).delete(synchronize_session=False)
    for model in (Claim, Evidence, Consent, SessionToken, Response):
        session.query(model).filter(model.user_id.in_(ids)).delete(synchronize_session=False)
    session.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    session.commit()
    print(f"  已清理 {len(ids)} 个演示账号及其关联数据")


def _submit_answers(session, *, user: User, answers: dict[str, str]) -> None:
    """走真实接口：写 Claim + Evidence + 熵引擎的 Elicitation/Response。"""
    if not answers:
        return
    submit_questionnaire(
        payload=QuestionnaireSubmissionIn(version=QUESTIONNAIRE_VERSION, answers=answers),
        user=user,
        db=session,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成前端联调用的演示数据")
    parser.add_argument("--reset", action="store_true", help="先删除演示账号（含配套账号）再重建")
    args = parser.parse_args(argv)

    if len(QUESTIONNAIRE["questions"]) < 2:
        print("题库异常：至少需要 2 道题", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        if args.reset:
            print("[0/6] 清理旧数据")
            _reset(session)

        print("[1/7] 创建 4 个演示账号 + 1 个配套账号（密码统一 password123）")
        users: list[User] = []
        for p in PERSONAS:
            u = _get_or_create_user(
                session,
                email=p["email"],
                display_name=p["display_name"],
                birth_year=p["birth_year"],
                region=p["region"],
            )
            users.append(u)
            print(f"      {p['display_name']}  <{p['email']}>  id={u.id}")
        partner = _get_or_create_user(
            session,
            email=CHAT_PARTNER["email"],
            display_name=CHAT_PARTNER["display_name"],
            birth_year=CHAT_PARTNER["birth_year"],
            region=CHAT_PARTNER["region"],
        )
        print(f"      {CHAT_PARTNER['display_name']}  <{CHAT_PARTNER['email']}>  id={partner.id}  (配套)")

        print("[2/7] 授权 matching:v1 / conversation:v1")
        for u in [*users, partner]:
            for scope in ("matching:v1", "conversation:v1"):
                post_consent(
                    payload=ConsentIn(scope=scope, purpose="用于演示环境联调"),
                    user=u,
                    db=session,
                )

        print("[3/7] 提交问卷（何枝故意不答，用于 EXPLORING 状态）")
        for p, u in zip(PERSONAS, users, strict=True):
            _submit_answers(session, user=u, answers=p["answers"])
            print(f"      {p['display_name']}: {len(p['answers'])} 项作答")

        print("[4/7] 只为「林屿」生成推荐（周聿要保留 SELF_PROFILE_READY）")
        try:
            out = create_recommendations(user=users[0], db=session)
            print(f"      林屿: {len(out.items)} 条推荐")
        except Exception as exc:  # noqa: BLE001 - 演示脚本，失败不该中断整体
            print(f"      林屿: 生成失败（{exc}）", file=sys.stderr)

        print("[5/7] 造关系：苏晚 <-> 温野 已 connected；林屿 -> 周聿 待回应")
        create_invitation(
            payload=InvitationIn(candidate_id=str(partner.id), message="想从一个具体场景开始了解。"),
            user=users[1],
            db=session,
        )
        create_invitation(
            payload=InvitationIn(candidate_id=str(users[1].id), message="我也想问同一个问题。"),
            user=partner,
            db=session,
        )
        create_invitation(
            payload=InvitationIn(candidate_id=str(users[2].id), message="你写的周末那件事我很有共鸣。"),
            user=users[0],
            db=session,
        )

        match = session.execute(
            select(Match).where(
                Match.user_a_id == min(int(users[1].id), int(partner.id)),
                Match.user_b_id == max(int(users[1].id), int(partner.id)),
            )
        ).scalar_one()
        print(f"      苏晚 <-> 温野 match_id={match.id} status={match.status}")

        print("[6/7] 写入 4 条聊天记录")
        existing = session.execute(
            select(MatchMessage).where(MatchMessage.match_id == match.id)
        ).scalars().all()
        if existing:
            print(f"      已有 {len(existing)} 条，跳过")
        else:
            senders = [int(partner.id), int(users[1].id)]
            for idx, (who, body) in enumerate(CHAT_LINES):
                session.add(
                    MatchMessage(
                        id=f"demo-msg-{idx + 1}",
                        match_id=match.id,
                        sender_id=senders[who],
                        body=body,
                        client_message_id=f"demo-uuid-{idx + 1}",
                    )
                )
            session.commit()
            print(f"      写入 {len(CHAT_LINES)} 条")

        print("[7/7] 校验各账号的 space/state")
        ok = True
        for p, u in zip(PERSONAS, users, strict=True):
            state = get_space_state(user=u, db=session)["state"]
            expect = p["intent"].split("（")[0]
            flag = "OK  " if state == expect else "MISMATCH"
            if state != expect:
                ok = False
            print(f"  [{flag}] {p['display_name']:<4} {p['email']:<20} state={state:<18} 预期 {expect}")
        pstate = get_space_state(user=partner, db=session)["state"]
        print(f"  [----] {CHAT_PARTNER['display_name']:<4} {CHAT_PARTNER['email']:<20} state={pstate:<18} （配套账号）")

        print("\n=== 登录信息 ===")
        print(f"  密码（所有账号相同）：{PASSWORD}")
        for p in [*PERSONAS, CHAT_PARTNER]:
            print(f"    {p['display_name']}  {p['email']}")

        print(
            "\n下一步：\n"
            "  1) 起后端：python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload\n"
            "  2) 前端按 docs/api/README.md 配同源代理，然后 POST /api/v1/auth/login 切换账号看四种界面\n"
            f"  3) 聊天页登录「苏晚」或「温野」，match_id={match.id}"
        )
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
