from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.errors import APIError
from app.api.v1.security import CurrentUser, SessionDep, new_id, now_utc
from app.models import Consent, Invitation, Match, User

router = APIRouter(prefix="/invitations", tags=["v1/invitations"])


class InvitationIn(BaseModel):
    candidate_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4000)


class InvitationOut(BaseModel):
    match_id: str
    status: str


def _require_conversation_consent(*, db: Session, user_id: int) -> None:
    row = (
        db.execute(
            select(Consent).where(
                Consent.user_id == user_id,
                Consent.scope == "conversation:v1",
                Consent.revoked_at.is_(None),
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        raise APIError(
            code="CONSENT_REQUIRED",
            message="需要先授权聊天用途",
            status_code=403,
            details={"scope": "conversation:v1"},
        )


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


@router.post("", response_model=InvitationOut)
def create_invitation(
    payload: InvitationIn, user: CurrentUser, db: SessionDep
) -> InvitationOut:
    try:
        candidate_id = int(payload.candidate_id)
    except ValueError:
        raise APIError(code="INVALID_CANDIDATE", message="candidate_id 不合法", status_code=400)

    if candidate_id == user.id:
        raise APIError(code="INVALID_CANDIDATE", message="不能邀请自己", status_code=400)

    cand = db.get(User, candidate_id)
    if cand is None:
        raise APIError(code="NOT_FOUND", message="candidate_not_found", status_code=404)

    _require_conversation_consent(db=db, user_id=int(user.id))
    _require_conversation_consent(db=db, user_id=int(cand.id))

    inv = (
        db.execute(
            select(Invitation).where(
                Invitation.from_user_id == user.id, Invitation.to_user_id == candidate_id
            )
        )
        .scalars()
        .one_or_none()
    )
    if inv is None:
        inv = Invitation(
            id=new_id(),
            from_user_id=int(user.id),
            to_user_id=int(candidate_id),
            message=payload.message,
        )
        db.add(inv)
    else:
        inv.message = payload.message
        db.add(inv)

    reverse_exists = (
        db.execute(
            select(Invitation).where(
                Invitation.from_user_id == candidate_id, Invitation.to_user_id == user.id
            )
        )
        .scalars()
        .first()
        is not None
    )

    a0, b0 = _pair(int(user.id), int(candidate_id))
    match = (
        db.execute(select(Match).where(and_(Match.user_a_id == a0, Match.user_b_id == b0)))
        .scalars()
        .one_or_none()
    )
    if match is None:
        match = Match(id=new_id(), user_a_id=a0, user_b_id=b0, status="pending", connected_at=None)
        db.add(match)

    if reverse_exists:
        match.status = "connected"
        match.connected_at = now_utc()
        db.add(match)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(code="INVITATION_CONFLICT", message="invite_conflict", status_code=409)

    return InvitationOut(match_id=match.id, status=match.status)
