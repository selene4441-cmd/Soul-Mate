from __future__ import annotations

import argparse
import os
import random
import sys
from array import array
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings  # noqa: E402
from app.models import (  # noqa: E402
    BehaviorEvent,
    BehaviorEventType,
    Elicitation,
    ElicitationKind,
    Profile,
    Response,
    User,
)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def openai_chat_complete(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_s: float = 30.0,
) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 256,
    }
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def generate_hidden_traits_summary(
    *,
    rng: random.Random,
    user_index: int,
    use_llm: bool,
) -> str:
    base_url = _env("OPENAI_BASE_URL", settings.openai_base_url)
    api_key = _env("OPENAI_API_KEY", settings.openai_api_key)
    model = _env("OPENAI_MODEL", settings.openai_model) or "gpt-5.2"

    archetypes = [
        "慢热理性",
        "外冷内热",
        "高敏感",
        "强共情",
        "好奇探索",
        "秩序控",
        "浪漫主义",
        "务实可靠",
        "边界感强",
        "幽默克制",
    ]
    values = ["自由", "安全感", "成长", "稳定", "新鲜感", "真诚", "效率", "陪伴", "审美", "成就"]
    conflict_style = ["回避冲突", "先冷静再沟通", "当场说开", "用幽默化解", "写下来表达"]
    love_language = ["高质量陪伴", "肯定鼓励", "实际行动", "礼物仪式感", "肢体接触"]

    traits = {
        "archetype": rng.choice(archetypes),
        "value": rng.choice(values),
        "conflict": rng.choice(conflict_style),
        "love": rng.choice(love_language),
        "detail": rng.choice(["会记住细节", "对氛围敏感", "需要独处充电", "讨厌敷衍", "喜欢有计划"]),
    }

    if use_llm and base_url and api_key:
        system = "你是中文人格画像写作助手。只输出一段画像描述，不要标题、不要列表、不要引用。"
        user = (
            "为虚拟用户生成一段约80个中文字符的“隐性特质”画像描述。"
            "要求：自然、具体、有可观察的偏好与互动风格；不要包含姓名、电话、邮箱、地址等个人信息；"
            f"参考特质：{traits}。"
        )
        text = openai_chat_complete(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        text = " ".join(text.split())
        if 60 <= len(text) <= 100:
            return text
        return text[:80]

    template = (
        "偏{archetype}，重视{value}；对关系细节{detail}，遇到分歧倾向{conflict}。"
        "表达爱更像{love}，慢慢建立信任后会更主动。"
    )
    return template.format(**traits)[:80]


def ensure_elicitations(session: Session, total_cards: int) -> list[Elicitation]:
    existing = session.execute(sa.select(Elicitation)).scalars().all()
    by_question = {e.question: e for e in existing}

    for i in range(1, total_cards + 1):
        question = f"Card {i}: 你更偏好哪种相处节奏？"
        if question in by_question:
            continue
        session.add(
            Elicitation(
                question=question,
                options=["慢慢来", "直接明确", "顺其自然", "一起制定计划"],
                kind=ElicitationKind.SINGLE_CHOICE,
            )
        )

    session.commit()
    return session.execute(sa.select(Elicitation).order_by(Elicitation.id)).scalars().all()


def ensure_users(session: Session, total_users: int) -> list[int]:
    existing_ids = session.execute(sa.select(User.id).order_by(User.id)).scalars().all()
    missing = total_users - len(existing_ids)
    if missing <= 0:
        return existing_ids[:total_users]

    for _ in range(missing):
        session.add(User(consent=True))
    session.commit()

    return session.execute(sa.select(User.id).order_by(User.id)).scalars().all()[:total_users]


def behavior_event_batch(
    *,
    rng: random.Random,
    user_id: int,
    count: int,
) -> list[BehaviorEvent]:
    now = datetime.now(UTC)
    events: list[BehaviorEvent] = []

    event_types = [
        BehaviorEventType.BROWSE,
        BehaviorEventType.DWELL,
        BehaviorEventType.LIKE,
        BehaviorEventType.SWIPE,
    ]
    weights = [0.45, 0.25, 0.10, 0.20]

    for i in range(count):
        event_type: BehaviorEventType = rng.choices(event_types, weights=weights, k=1)[0]
        created_at = now - timedelta(
            seconds=rng.randint(10, 89) * i,
            minutes=rng.randint(0, 9),
            days=rng.randint(0, 29),
        )

        if event_type == BehaviorEventType.DWELL:
            # 停留时长：对数正态分布（单位 ms），裁剪到 [200ms, 5min]
            ms = int(rng.lognormvariate(mu=8.99, sigma=0.7))  # exp(8.99) ~= 8000
            duration_ms = max(200, min(ms, 300_000))
        elif event_type == BehaviorEventType.BROWSE:
            duration_ms = rng.randint(200, 7_999)
        elif event_type == BehaviorEventType.SWIPE:
            duration_ms = rng.randint(50, 1_499)
        else:
            duration_ms = rng.randint(50, 599)

        events.append(
            BehaviorEvent(
                user_id=user_id,
                event_type=event_type,
                duration_ms=duration_ms,
                created_at=created_at,
            )
        )

    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic dataset into database (idempotent).")
    parser.add_argument("--users", type=int, default=500)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--max-events", type=int, default=200)
    parser.add_argument("--cards", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260912)
    parser.add_argument("--no-llm", action="store_true", help="Do not call LLM; use deterministic fallback.")
    args = parser.parse_args(argv)

    if args.users < 1:
        raise SystemExit("--users must be >= 1")
    if args.min_events < 0:
        raise SystemExit("--min-events must be >= 0")
    if args.max_events < args.min_events:
        raise SystemExit("--max-events must be >= --min-events")
    if args.cards < 0:
        raise SystemExit("--cards must be >= 0")

    db_url = _env("DATABASE_URL", settings.database_url)
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set and no default is configured.")

    engine = sa.create_engine(db_url, future=True)

    with Session(engine) as session:
        elicitations = ensure_elicitations(session, total_cards=args.cards) if args.cards else []
        user_ids = ensure_users(session, total_users=args.users)

        for idx, user_id in enumerate(user_ids, start=1):
            base_seed = args.seed ^ (user_id * 1_000_003)
            rng_profile = random.Random(base_seed ^ 0xA17E_0001)
            rng_events = random.Random(base_seed ^ 0xA17E_0002)
            rng_responses = random.Random(base_seed ^ 0xA17E_0003)

            # Profile: create once as a marker for idempotency.
            existing_profile = session.get(Profile, user_id)
            if existing_profile is None:
                summary = generate_hidden_traits_summary(
                    rng=rng_profile, user_index=idx, use_llm=not args.no_llm
                )
                emb = array("f", [float(rng_profile.gauss(0.0, 1.0)) for _ in range(128)]).tobytes()
                session.add(Profile(user_id=user_id, summary=summary, embedding=emb))
                session.commit()

            # Behavior events: top-up to deterministic target count.
            target_events = rng_events.randint(args.min_events, args.max_events)
            existing_events = session.execute(
                sa.select(sa.func.count()).select_from(BehaviorEvent).where(BehaviorEvent.user_id == user_id)
            ).scalar_one()
            to_create = max(0, int(target_events) - int(existing_events))
            if to_create:
                session.add_all(behavior_event_batch(rng=rng_events, user_id=user_id, count=to_create))
                session.commit()

            # Responses: ensure one response per user per elicitation.
            if not elicitations:
                continue

            existing_response_elicitation_ids = set(
                session.execute(sa.select(Response.elicitation_id).where(Response.user_id == user_id)).scalars()
            )

            new_responses: list[Response] = []
            for elicitation in elicitations:
                if elicitation.id in existing_response_elicitation_ids:
                    continue

                options = elicitation.options
                if isinstance(options, list) and options:
                    choice = str(rng_responses.choice(options))
                elif isinstance(options, dict) and options:
                    choice = str(rng_responses.choice(list(options.keys())))
                else:
                    choice = "unknown"

                rt = int(rng_responses.gauss(900, 350))
                reaction_time_ms = max(120, min(rt, 8000))
                new_responses.append(
                    Response(
                        user_id=user_id,
                        elicitation_id=elicitation.id,
                        choice=choice,
                        reaction_time_ms=reaction_time_ms,
                    )
                )

            if new_responses:
                session.add_all(new_responses)
                session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
