from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.v1.questionnaire_def import QUESTIONNAIRE
from app.api.v1.security import CurrentUser, SessionDep
from app.models import Claim, Consent, Match, RecommendationSession

router = APIRouter(prefix="/space", tags=["v1/space"])


def _has_consent(*, db: Session, user_id: int, scope: str) -> bool:
    return (
        db.execute(
            select(Consent.id).where(
                Consent.user_id == user_id, Consent.scope == scope, Consent.revoked_at.is_(None)
            )
        )
        .first()
        is not None
    )


@router.get("/state")
def get_space_state(user: CurrentUser, db: SessionDep) -> dict[str, Any]:
    claims = db.execute(select(Claim).where(Claim.user_id == user.id)).scalars().all()
    answered = {c.dimension for c in claims}

    questions = QUESTIONNAIRE["questions"]
    next_q = None
    for q in questions:
        if q["dimension"] not in answered:
            next_q = q
            break
    if next_q is None and questions:
        next_q = questions[0]

    q_out = None
    if next_q is not None:
        q_out = {
            "id": next_q["id"],
            "dimension": next_q["dimension"],
            "prompt": next_q["prompt"],
            "options": [],
        }

    if (
        db.execute(
            select(Match.id).where(
                or_(Match.user_a_id == user.id, Match.user_b_id == user.id),
                Match.status == "connected",
            )
        ).first()
        is not None
    ):
        return {"state": "CHAT", "question": q_out, "profile": None, "can_match": True}

    has_matching = _has_consent(db=db, user_id=int(user.id), scope="matching:v1")
    required_dims = {q["dimension"] for q in questions if q.get("required")}
    completed = required_dims.issubset(answered)
    can_match = bool(has_matching and completed)

    if not can_match:
        return {"state": "EXPLORING", "question": q_out, "profile": None, "can_match": False}

    has_recos = (
        db.execute(select(RecommendationSession.id).where(RecommendationSession.user_id == user.id))
        .first()
        is not None
    )
    if has_recos:
        return {"state": "MATCHING", "question": q_out, "profile": None, "can_match": True}
    return {"state": "SELF_PROFILE_READY", "question": q_out, "profile": None, "can_match": True}
