from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Claim, Consent, Evidence, ModelVersion, PolicyVersion, User
from app.questionnaire_data import (
    QUESTIONNAIRE_VERSION,
    claim_expiry,
    get_questionnaire,
    option_map,
)
from app.security import hash_password, stable_hash

BASE_ANSWERS = {
    "relationship_goal": "long_term",
    "region_preference": "same_region",
    "age_preference": "open",
    "marital_status": "never_married",
    "value_family": "balanced",
    "value_career": "discuss_balance",
    "value_integrity": "explain_early",
    "value_freedom": "shared_rhythm",
    "nonneg_long_distance": "can_plan",
    "nonneg_children": "open",
    "nonneg_social_intensity": "sometimes",
    "nonneg_spending": "plan_ratio",
    "growth_direction": "life_balance",
    "growth_pace": "steady_change",
    "growth_autonomy": "support_autonomy",
    "growth_repair": "seek_method",
    "life_weekend": "home",
    "life_work_intensity": "regular",
    "comm_directness": "direct",
    "comm_reply_frequency": "daily",
    "comm_depth": "daily_share",
    "repair_style": "pause_then_talk",
    "emotional_support": "listen",
    "time_reply_expectation": "advance_note",
    "time_change_notice": "early_notice",
    "space_solitude": "weekly",
    "space_privacy": "case_by_case",
    "safety_boundary_response": "stop_and_report",
}

CANDIDATES = [
    {
        "display_name": "林岚",
        "email": "demo.linlan@tongpin.local",
        "birth_year": 1994,
        "region": "上海",
        "answers": {"growth_direction": "life_balance", "comm_depth": "deep_topics"},
    },
    {
        "display_name": "周屿",
        "email": "demo.zhouyu@tongpin.local",
        "birth_year": 1992,
        "region": "上海",
        "answers": {"value_career": "career_priority", "life_weekend": "outdoor"},
    },
    {
        "display_name": "顾宁",
        "email": "demo.guning@tongpin.local",
        "birth_year": 1995,
        "region": "杭州",
        "answers": {"value_freedom": "high_autonomy", "space_solitude": "daily"},
    },
    {
        "display_name": "沈知夏",
        "email": "demo.shenzhixia@tongpin.local",
        "birth_year": 1993,
        "region": "上海",
        "answers": {"growth_direction": "career_learning", "comm_reply_frequency": "needs_space"},
    },
    {
        "display_name": "陈聿",
        "email": "demo.chenyu@tongpin.local",
        "birth_year": 1991,
        "region": "苏州",
        "answers": {"repair_style": "show_care", "emotional_support": "presence"},
    },
    {
        "display_name": "唐予",
        "email": "demo.tangyu@tongpin.local",
        "birth_year": 1996,
        "region": "上海",
        "answers": {"growth_direction": "exploration", "time_reply_expectation": "reply_when_free"},
    },
]


def _create_claims(db: Session, user: User, answers: dict[str, str]) -> None:
    question_map = {item["id"]: item for item in get_questionnaire()["questions"]}
    now = datetime.now(timezone.utc)
    for qid, value in answers.items():
        question = question_map[qid]
        evidence = Evidence(
            user_id=user.id,
            source_type="seed_questionnaire",
            source_ref=f"{QUESTIONNAIRE_VERSION}:{qid}",
            excerpt_hash=stable_hash(f"{user.email}:{qid}:{value}"),
            summary=option_map(question)[value],
            collected_at=now,
            consent_scope="matching:v1",
        )
        db.add(evidence)
        db.flush()
        db.add(
            Claim(
                user_id=user.id,
                dimension=question["dimension"],
                value=value,
                claim_type=question["claim_type"],
                evidence_ids=[evidence.id],
                confidence=0.94,
                stability=question["stability"],
                observed_at=now,
                expires_at=claim_expiry(question["stability"]),
                sensitivity=question["sensitivity"],
                user_editable=True,
                user_confirmed=True,
            )
        )


def _seed_candidate(db: Session, candidate: dict) -> User:
    answers = {**BASE_ANSWERS, **candidate["answers"]}
    user = User(
        display_name=candidate["display_name"],
        email=candidate["email"],
        password_hash=hash_password("disabled-seed-account"),
        birth_year=candidate["birth_year"],
        region=candidate["region"],
        role="user",
        status="active",
        is_seed=True,
    )
    db.add(user)
    db.flush()
    settings = get_settings()
    for scope, purpose in (
        ("matching:v1", "用于展示可解释的关系线索"),
        ("conversation:v1", "用于演示双方同意后的交流"),
        ("outcomes:v1", "用于演示关系结果反馈"),
    ):
        db.add(
            Consent(
                user_id=user.id,
                scope=scope,
                version=settings.consent_version,
                purpose=purpose,
            )
        )
    _create_claims(db, user, answers)
    return user


def seed_demo_data(db: Session) -> None:
    settings = get_settings()
    if not db.get(ModelVersion, settings.model_version):
        db.add(
            ModelVersion(
                id=settings.model_version,
                description="规则、Claim 覆盖与基础关系信号",
            )
        )
    if not db.get(PolicyVersion, settings.policy_version):
        db.add(
            PolicyVersion(
                id=settings.policy_version,
                description="冷启动策略，含探索位置与完整曝光日志",
            )
        )
    if not db.scalar(select(User.id).where(User.is_seed.is_(True))):
        for candidate in CANDIDATES:
            _seed_candidate(db, candidate)
    db.commit()
