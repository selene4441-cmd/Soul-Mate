from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Claim, Evidence, User
from app.modules.audit import record_audit
from app.questionnaire_data import (
    QUESTIONNAIRE_VERSION,
    claim_expiry,
    get_questionnaire,
    option_map,
    validate_answers,
)
from app.schemas import (
    ClaimFeedbackRequest,
    ClaimResponse,
    ClaimUpdateRequest,
    QuestionnaireSubmission,
)
from app.security import stable_hash


def submit_questionnaire(
    db: Session,
    user: User,
    submission: QuestionnaireSubmission,
) -> list[ClaimResponse]:
    if submission.version != QUESTIONNAIRE_VERSION:
        raise DomainError(
            "QUESTIONNAIRE_VERSION_MISMATCH", "问卷版本已更新，请刷新后重试", status_code=409
        )
    try:
        validate_answers(submission.answers)
    except ValueError as exc:
        raise DomainError("INVALID_ANSWERS", str(exc), status_code=422) from exc

    question_map = {item["id"]: item for item in get_questionnaire()["questions"]}
    now = datetime.now(timezone.utc)
    created: list[Claim] = []
    for index, (qid, value) in enumerate(submission.answers.items()):
        question = question_map[qid]
        labels = option_map(question)
        values = value if isinstance(value, list) else [value]
        summary = "、".join(labels[item] for item in values)
        evidence = Evidence(
            user_id=user.id,
            source_type="questionnaire",
            source_ref=f"{QUESTIONNAIRE_VERSION}:{qid}",
            excerpt_hash=stable_hash(f"{qid}:{value!r}"),
            summary=summary,
            collected_at=now + __import__("datetime").timedelta(microseconds=index),
            consent_scope="matching:v1",
        )
        db.add(evidence)
        db.flush()
        existing = db.scalar(
            select(Claim).where(
                Claim.user_id == user.id,
                Claim.dimension == question["dimension"],
                or_(Claim.correction_state.is_(None), Claim.correction_state != "deleted"),
            )
        )
        if existing:
            existing.value = value
            existing.claim_type = question["claim_type"]
            existing.evidence_ids = [evidence.id]
            existing.confidence = 0.92
            existing.stability = question["stability"]
            existing.observed_at = now
            existing.expires_at = claim_expiry(question["stability"])
            existing.sensitivity = question["sensitivity"]
            existing.user_confirmed = True
            existing.correction_state = None
            claim = existing
        else:
            claim = Claim(
                user_id=user.id,
                dimension=question["dimension"],
                value=value,
                claim_type=question["claim_type"],
                evidence_ids=[evidence.id],
                confidence=0.92,
                stability=question["stability"],
                observed_at=now,
                expires_at=claim_expiry(question["stability"]),
                sensitivity=question["sensitivity"],
                user_editable=True,
                user_confirmed=True,
            )
            db.add(claim)
        created.append(claim)
    record_audit(
        db,
        actor_id=user.id,
        action="questionnaire.submitted",
        entity_type="user",
        entity_id=user.id,
        metadata_safe={"question_count": len(created)},
    )
    db.commit()
    for claim in created:
        db.refresh(claim)
    return [ClaimResponse.model_validate(claim) for claim in created]


def list_claims(db: Session, user: User, include_expired: bool = False) -> list[ClaimResponse]:
    query = select(Claim).where(
        Claim.user_id == user.id,
        or_(Claim.correction_state.is_(None), Claim.correction_state != "deleted"),
    )
    if not include_expired:
        query = query.where(Claim.expires_at > datetime.now(timezone.utc))
    rows = db.scalars(query.order_by(Claim.dimension.asc())).all()
    return [ClaimResponse.model_validate(row) for row in rows]


def feedback_claim(
    db: Session,
    user: User,
    claim_id: str,
    payload: ClaimFeedbackRequest,
) -> ClaimResponse:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id, Claim.user_id == user.id))
    if not claim:
        raise DomainError("CLAIM_NOT_FOUND", "未找到该关系信号", status_code=404)
    claim.correction_state = payload.feedback
    if payload.feedback == "more_like_this":
        claim.user_confirmed = True
        claim.confidence = min(0.99, claim.confidence + 0.05)
    elif payload.feedback == "not_like_this":
        claim.user_confirmed = False
        claim.confidence = max(0.05, claim.confidence - 0.35)
    else:
        claim.user_confirmed = False
        claim.confidence = min(claim.confidence, 0.5)
    record_audit(
        db,
        actor_id=user.id,
        action=f"claim.{payload.feedback}",
        entity_type="claim",
        entity_id=claim.id,
        metadata_safe={"dimension": claim.dimension},
    )
    db.commit()
    db.refresh(claim)
    return ClaimResponse.model_validate(claim)


def update_claim(
    db: Session,
    user: User,
    claim_id: str,
    payload: ClaimUpdateRequest,
) -> ClaimResponse:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id, Claim.user_id == user.id))
    if not claim:
        raise DomainError("CLAIM_NOT_FOUND", "未找到该关系信号", status_code=404)
    if not claim.user_editable:
        raise DomainError("CLAIM_NOT_EDITABLE", "该信号当前不可修改", status_code=403)
    claim.value = payload.value
    claim.user_confirmed = payload.user_confirmed
    claim.correction_state = "edited"
    claim.confidence = 0.95 if payload.user_confirmed else 0.6
    db.commit()
    db.refresh(claim)
    record_audit(
        db,
        actor_id=user.id,
        action="claim.updated",
        entity_type="claim",
        entity_id=claim.id,
        metadata_safe={"dimension": claim.dimension},
    )
    db.commit()
    return ClaimResponse.model_validate(claim)


def delete_claim(db: Session, user: User, claim_id: str) -> None:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id, Claim.user_id == user.id))
    if not claim:
        raise DomainError("CLAIM_NOT_FOUND", "未找到该关系信号", status_code=404)
    claim.correction_state = "deleted"
    claim.user_confirmed = False
    record_audit(
        db,
        actor_id=user.id,
        action="claim.deleted",
        entity_type="claim",
        entity_id=claim.id,
        metadata_safe={"dimension": claim.dimension},
    )
    db.commit()
