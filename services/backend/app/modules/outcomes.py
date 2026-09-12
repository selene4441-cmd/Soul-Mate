from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import has_active_consent
from app.errors import DomainError
from app.models import Outcome, User
from app.schemas import OutcomeCreate, OutcomeResponse


def _good_outcome(outcome: Outcome) -> bool:
    if outcome.safety_event or outcome.satisfaction != "positive" or not outcome.continued_contact:
        return False
    if outcome.window_days >= 30:
        return outcome.growth_alignment == "positive" and outcome.boundary_respect == "positive"
    return True


def submit_outcome(db: Session, user: User, payload: OutcomeCreate) -> OutcomeResponse:
    if not has_active_consent(db, user.id, "outcomes:v1"):
        raise DomainError(
            "CONSENT_REQUIRED",
            "需要先授权结果反馈用途",
            status_code=403,
            details={"scope": "outcomes:v1"},
        )
    if payload.window_days == 30 and (
        payload.growth_alignment is None or payload.boundary_respect is None
    ):
        raise DomainError(
            "OUTCOME_FIELDS_REQUIRED", "30 天反馈需要成长同向与边界尊重信息", status_code=422
        )
    outcome = db.scalar(
        select(Outcome).where(
            Outcome.user_id == user.id,
            Outcome.candidate_id == payload.candidate_id,
            Outcome.window_days == payload.window_days,
        )
    )
    if outcome:
        outcome.match_id = payload.match_id
        outcome.satisfaction = payload.satisfaction
        outcome.growth_alignment = payload.growth_alignment
        outcome.boundary_respect = payload.boundary_respect
        outcome.continued_contact = payload.continued_contact
        outcome.safety_event = payload.safety_event
    else:
        outcome = Outcome(user_id=user.id, **payload.model_dump())
        db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return OutcomeResponse(
        id=outcome.id,
        candidate_id=outcome.candidate_id,
        window_days=outcome.window_days,
        satisfaction=outcome.satisfaction,
        growth_alignment=outcome.growth_alignment,
        boundary_respect=outcome.boundary_respect,
        continued_contact=outcome.continued_contact,
        good_outcome=_good_outcome(outcome),
        submitted_at=outcome.submitted_at,
    )


def list_outcomes(db: Session, user: User) -> list[OutcomeResponse]:
    rows = db.scalars(
        select(Outcome).where(Outcome.user_id == user.id).order_by(Outcome.submitted_at.desc())
    ).all()
    return [
        OutcomeResponse(
            id=row.id,
            candidate_id=row.candidate_id,
            window_days=row.window_days,
            satisfaction=row.satisfaction,
            growth_alignment=row.growth_alignment,
            boundary_respect=row.boundary_respect,
            continued_contact=row.continued_contact,
            good_outcome=_good_outcome(row),
            submitted_at=row.submitted_at,
        )
        for row in rows
    ]
