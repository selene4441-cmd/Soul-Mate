from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import has_active_consent
from app.errors import DomainError
from app.models import Claim, Impression, PairFeature, SafetyEvent, User, UserAction
from app.questionnaire_data import DIMENSION_LABELS
from app.schemas import ActionRequest, CandidateLead, RecommendationBundle

CORE_DIMENSIONS = [
    "relationship_goal",
    "region_preference",
    "age_preference",
    "marital_status",
    "value_family",
    "value_career",
    "value_integrity",
    "value_freedom",
    "growth_direction",
    "growth_pace",
    "growth_autonomy",
    "growth_repair",
    "life_weekend",
    "life_work_intensity",
    "comm_directness",
    "comm_reply_frequency",
    "comm_depth",
    "repair_style",
    "emotional_support",
    "time_reply_expectation",
    "time_change_notice",
    "space_solitude",
    "space_privacy",
]
HARD_DIMENSIONS = {"relationship_goal", "region_preference", "age_preference", "marital_status"}
AGE_RANGES = {"25_32": (25, 32), "30_38": (30, 38), "35_45": (35, 45)}
REGION_GROUPS = {
    "上海": "yangtze",
    "杭州": "yangtze",
    "苏州": "yangtze",
    "南京": "yangtze",
    "北京": "north",
    "天津": "north",
    "广州": "south",
    "深圳": "south",
}
NON_NEGOTIABLE_CONFLICTS = [
    ("nonneg_long_distance", {"not_acceptable"}, {"must_resolve", "can_plan"}),
    ("nonneg_children", {"do_not_want"}, {"want"}),
    ("nonneg_children", {"want"}, {"do_not_want"}),
    ("nonneg_social_intensity", {"prefer_quiet"}, {"enjoy_frequent"}),
    ("nonneg_spending", {"save_first"}, {"enjoy_now"}),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _claim_maps(db: Session, user_id: str) -> dict[str, Claim]:
    rows = db.scalars(
        select(Claim)
        .where(
            Claim.user_id == user_id,
            or_(Claim.correction_state.is_(None), Claim.correction_state != "deleted"),
            Claim.expires_at > _now(),
            Claim.confidence >= 0.5,
            Claim.user_confirmed.is_(True),
        )
        .order_by(Claim.observed_at.desc())
    ).all()
    claims: dict[str, Claim] = {}
    for claim in rows:
        claims.setdefault(claim.dimension, claim)
    return claims


def _age(birth_year: int) -> int:
    return _now().year - birth_year


def _age_allowed(preference: str, age: int) -> bool:
    if preference == "open":
        return True
    bounds = AGE_RANGES.get(preference)
    return bool(bounds and bounds[0] <= age <= bounds[1])


def _region_allowed(*, viewer: User, viewer_claim: Claim | None, candidate: User) -> bool:
    preference = str(viewer_claim.value) if viewer_claim else "same_region"
    if preference == "remote_ok":
        return True
    if preference == "same_city":
        return viewer.region == candidate.region
    return REGION_GROUPS.get(viewer.region, viewer.region) == REGION_GROUPS.get(
        candidate.region, candidate.region
    )


def _safety_denied(db: Session, candidate_id: str) -> bool:
    denied = db.scalar(
        select(SafetyEvent.id).where(
            SafetyEvent.subject_id == candidate_id,
            SafetyEvent.status.in_(["pending", "confirmed"]),
            SafetyEvent.severity.in_(["high", "critical"]),
        )
    )
    return denied is not None


def _hard_constraints(
    db: Session,
    viewer: User,
    candidate: User,
    a: dict[str, Claim],
    b: dict[str, Claim],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not all(dimension in a and dimension in b for dimension in HARD_DIMENSIONS):
        return False, ["required_claims_missing"]
    if str(a["relationship_goal"].value) != str(b["relationship_goal"].value):
        failures.append("relationship_goal_conflict")
    if not _region_allowed(viewer=viewer, viewer_claim=a["region_preference"], candidate=candidate):
        failures.append("region_conflict")
    if not _region_allowed(viewer=candidate, viewer_claim=b["region_preference"], candidate=viewer):
        failures.append("reverse_region_conflict")
    if not _age_allowed(str(a["age_preference"].value), _age(candidate.birth_year)):
        failures.append("age_preference_conflict")
    if not _age_allowed(str(b["age_preference"].value), _age(viewer.birth_year)):
        failures.append("reverse_age_preference_conflict")
    if str(a["marital_status"].value) != str(b["marital_status"].value):
        failures.append("marital_status_conflict")
    for dimension, left_values, right_values in NON_NEGOTIABLE_CONFLICTS:
        left = a.get(dimension)
        right = b.get(dimension)
        if left and right and str(left.value) in left_values and str(right.value) in right_values:
            failures.append(f"{dimension}_conflict")
    return not failures, failures


def _overlap(a: Claim, b: Claim) -> bool:
    return bool(set(_as_list(a.value)) & set(_as_list(b.value)))


def _build_explanation(
    a: dict[str, Claim], b: dict[str, Claim]
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    common: list[str] = []
    differences: list[str] = []
    unknown: list[str] = []
    evidence_ids: list[str] = []
    shared_dimensions: list[str] = []

    for dimension in CORE_DIMENSIONS:
        left = a.get(dimension)
        right = b.get(dimension)
        label = DIMENSION_LABELS[dimension]
        if not left or not right:
            unknown.append(f"目前还不知道你们在“{label}”上的实际相处感受。")
            continue
        if _overlap(left, right):
            shared_dimensions.append(dimension)
            common.append(f"你们在“{label}”上的当前选择比较接近，可能更容易从相似期待开始沟通。")
            evidence_ids.extend(left.evidence_ids)
        elif dimension not in HARD_DIMENSIONS:
            differences.append(
                f"在“{label}”上，你们目前的取舍不同，可能需要先确认彼此在具体情境中的感受。"
            )

    if not unknown:
        unknown.append(
            "现在仍然不知道你们在真实忙碌、冲突和计划变化时会怎样回应，需要继续相处确认。"
        )
    continuations = [
        "可以从一个具体场景聊起，例如忙碌时怎样保持联系、计划变化时怎样说明。",
        "继续留意对方是否尊重你的时间、空间和已表达的边界。",
        "把现在的相似理解为可讨论的线索，而不是对相处结果的确定判断。",
    ]
    if "growth_direction" in shared_dimensions or "growth_pace" in shared_dimensions:
        continuations.insert(0, "可以进一步聊聊未来一年的变化计划，以及彼此希望怎样支持自主成长。")
    if "time_reply_expectation" in shared_dimensions or "space_solitude" in shared_dimensions:
        continuations.insert(0, "可以确认忙碌、独处和重新联系时的具体预期，减少时间与空间压力。")
    return common[:4], differences[:4], unknown[:4], continuations[:3], evidence_ids[:8]


def _headline(user: User, claims: dict[str, Claim]) -> str:
    goal = claims.get("relationship_goal")
    direction = claims.get("growth_direction")
    goal_text = {
        "long_term": "目前希望建立长期稳定关系",
        "marriage": "目前以婚姻为关系方向",
        "dating": "目前希望先约会认识",
    }.get(str(goal.value) if goal else "", "目前仍在确认关系目标")
    direction_text = {
        "career_learning": "重视持续学习",
        "life_balance": "重视生活平衡",
        "family_building": "重视家庭建设",
        "exploration": "愿意探索新的生活方向",
    }.get(str(direction.value) if direction else "", "也在确认未来节奏")
    return f"{user.region} · {goal_text}，{direction_text}"


def _score_pair(a: dict[str, Claim], b: dict[str, Claim]) -> tuple[float, float, list[str]]:
    scores: list[float] = []
    evidence_count = 0
    shared_dimensions: list[str] = []
    for dimension in CORE_DIMENSIONS:
        left = a.get(dimension)
        right = b.get(dimension)
        if not left or not right:
            scores.append(-0.35)
            continue
        evidence_count += len(left.evidence_ids) + len(right.evidence_ids)
        if _overlap(left, right):
            weight = 2.0 if dimension.startswith(("value_", "growth_")) else 1.0
            scores.append(weight * min(left.confidence, right.confidence))
            shared_dimensions.append(dimension)
        else:
            scores.append(-0.2)
    internal_score = sum(scores) / max(len(scores), 1)
    coverage = sum(1 for dimension in CORE_DIMENSIONS if dimension in a and dimension in b) / len(
        CORE_DIMENSIONS
    )
    return internal_score, coverage, shared_dimensions


def _save_pair_features(
    db: Session,
    viewer: User,
    candidate: User,
    internal_score: float,
    coverage: float,
    shared_dimensions: list[str],
) -> None:
    settings = get_settings()
    features = {
        "P1": {"passed": True},
        "P2": {"shared_dimensions": shared_dimensions},
        "P3": {"conflicts": 0},
        "P11": {"growth_aligned": any(item.startswith("growth_") for item in shared_dimensions)},
        "P12": {"time_boundary_aligned": "time_reply_expectation" in shared_dimensions},
        "P13": {"space_boundary_aligned": "space_solitude" in shared_dimensions},
        "internal": {"ranking_score": round(internal_score, 6)},
    }
    for feature_id, value in features.items():
        db.add(
            PairFeature(
                user_a_id=viewer.id,
                user_b_id=candidate.id,
                feature_id=feature_id,
                value=value,
                confidence=coverage,
                coverage=coverage,
                model_version=settings.model_version,
            )
        )


def _lead_for(
    viewer: User,
    candidate: User,
    a: dict[str, Claim],
    b: dict[str, Claim],
    recommendation_id: str,
) -> CandidateLead:
    common, differences, unknown, continuations, evidence_ids = _build_explanation(a, b)
    return CandidateLead(
        recommendation_id=recommendation_id,
        candidate_id=candidate.id,
        display_name=candidate.display_name,
        headline=_headline(candidate, b),
        common_signals=common,
        differences=differences,
        unknowns=unknown,
        how_to_continue=continuations,
        evidence_ids=evidence_ids,
    )


def generate_recommendations(
    db: Session,
    viewer: User,
    *,
    session_id: str,
    limit: int = 6,
) -> RecommendationBundle:
    settings = get_settings()
    if not has_active_consent(db, viewer.id, "matching:v1"):
        raise DomainError(
            "CONSENT_REQUIRED",
            "需要先授权匹配用途",
            status_code=403,
            details={"scope": "matching:v1"},
        )
    viewer_claims = _claim_maps(db, viewer.id)
    if not all(item in viewer_claims for item in HARD_DIMENSIONS):
        raise DomainError("PROFILE_INCOMPLETE", "请先完成关系目标与基础条件", status_code=409)

    candidates = db.scalars(
        select(User).where(
            User.id != viewer.id,
            User.status == "active",
            User.is_seed.is_(True),
        )
    ).all()
    eligible: list[tuple[float, User, dict[str, Claim], float, list[str]]] = []
    for candidate in candidates:
        if not has_active_consent(db, candidate.id, "matching:v1") or _safety_denied(
            db, candidate.id
        ):
            continue
        candidate_claims = _claim_maps(db, candidate.id)
        passed, _failures = _hard_constraints(
            db, viewer, candidate, viewer_claims, candidate_claims
        )
        if not passed:
            continue
        internal_score, coverage, shared_dimensions = _score_pair(viewer_claims, candidate_claims)
        eligible.append((internal_score, candidate, candidate_claims, coverage, shared_dimensions))

    eligible.sort(key=lambda row: (-row[0], row[1].id))
    if len(eligible) >= 4:
        eligible[-1], eligible[-2] = eligible[-2], eligible[-1]

    recommendation_id = uuid4().hex
    items: list[CandidateLead] = []
    for position, (score, candidate, candidate_claims, coverage, shared_dimensions) in enumerate(
        eligible[: max(1, min(limit, 12))], start=1
    ):
        _save_pair_features(db, viewer, candidate, score, coverage, shared_dimensions)
        items.append(
            _lead_for(viewer, candidate, viewer_claims, candidate_claims, recommendation_id)
        )
        db.add(
            Impression(
                recommendation_id=recommendation_id,
                user_id=viewer.id,
                candidate_id=candidate.id,
                session_id=session_id,
                rank=position,
                position=position,
                model_version=settings.model_version,
                policy_version=settings.policy_version,
                context={
                    "surface": "recommendations",
                    "exploration_slot": position == len(eligible[:limit]),
                },
                consent_scope="matching:v1",
            )
        )
    db.commit()
    return RecommendationBundle(
        generated_at=_now(),
        session_id=session_id,
        items=items,
    )


def get_candidate_lead(db: Session, viewer: User, candidate_id: str) -> CandidateLead:
    if not has_active_consent(db, viewer.id, "matching:v1"):
        raise DomainError("CONSENT_REQUIRED", "需要先授权匹配用途", status_code=403)
    candidate = db.get(User, candidate_id)
    if not candidate or candidate.status != "active" or candidate.is_seed is not True:
        raise DomainError("CANDIDATE_NOT_FOUND", "未找到该候选人", status_code=404)
    viewer_claims = _claim_maps(db, viewer.id)
    candidate_claims = _claim_maps(db, candidate.id)
    passed, _ = _hard_constraints(db, viewer, candidate, viewer_claims, candidate_claims)
    if not passed or _safety_denied(db, candidate.id):
        raise DomainError("CANDIDATE_UNAVAILABLE", "该候选人当前不可推荐", status_code=404)
    impression = db.scalar(
        select(Impression)
        .where(Impression.user_id == viewer.id, Impression.candidate_id == candidate.id)
        .order_by(Impression.event_time.desc())
    )
    recommendation_id = impression.recommendation_id if impression else uuid4().hex
    return _lead_for(viewer, candidate, viewer_claims, candidate_claims, recommendation_id)


def record_action(
    db: Session,
    viewer: User,
    candidate_id: str,
    payload: ActionRequest,
) -> None:
    candidate = db.get(User, candidate_id)
    if not candidate or candidate.status != "active":
        raise DomainError("CANDIDATE_NOT_FOUND", "未找到该候选人", status_code=404)
    impression = db.scalar(
        select(Impression)
        .where(Impression.user_id == viewer.id, Impression.candidate_id == candidate_id)
        .order_by(Impression.event_time.desc())
    )
    db.add(
        UserAction(
            user_id=viewer.id,
            candidate_id=candidate_id,
            recommendation_id=impression.recommendation_id if impression else None,
            action_type=payload.action,
            context={"source": "recommendation_card"},
        )
    )
    db.commit()
