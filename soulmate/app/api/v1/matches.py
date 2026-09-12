from __future__ import annotations

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.errors import APIError
from app.api.v1.security import CurrentUser, SessionDep, as_utc, new_id
from app.models import Consent, Match, MatchMessage

router = APIRouter(prefix="/matches", tags=["v1/matches"])


def _dt_z(dt) -> str:
    return as_utc(dt).isoformat().replace("+00:00", "Z")


class MatchOut(BaseModel):
    match_id: str
    candidate_id: str
    status: str
    connected_at: str | None


class MessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    client_message_id: str = Field(..., min_length=1, max_length=128)


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    body: str
    client_message_id: str
    created_at: str
    read_at: str | None


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


def _require_match(*, db: Session, match_id: str, user_id: int) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise APIError(code="NOT_FOUND", message="match_not_found", status_code=404)
    if user_id not in {match.user_a_id, match.user_b_id}:
        raise APIError(code="FORBIDDEN", message="not_in_match", status_code=403)
    return match


@router.get("", response_model=list[MatchOut])
def list_matches(user: CurrentUser, db: SessionDep) -> list[MatchOut]:
    rows = (
        db.execute(
            select(Match)
            .where(or_(Match.user_a_id == user.id, Match.user_b_id == user.id))
            .order_by(Match.connected_at.desc().nullslast(), Match.created_at.desc())
        )
        .scalars()
        .all()
    )
    out: list[MatchOut] = []
    for row in rows:
        candidate_id = row.user_b_id if row.user_a_id == user.id else row.user_a_id
        out.append(
            MatchOut(
                match_id=row.id,
                candidate_id=str(candidate_id),
                status=row.status,
                connected_at=_dt_z(row.connected_at) if row.connected_at else None,
            )
        )
    return out


@router.get("/{match_id}/messages", response_model=list[MessageOut])
def get_messages(
    user: CurrentUser,
    db: SessionDep,
    match_id: str = Path(..., min_length=1, max_length=128),
) -> list[MessageOut]:
    match = _require_match(db=db, match_id=match_id, user_id=int(user.id))
    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    _require_conversation_consent(db=db, user_id=int(user.id))
    _require_conversation_consent(db=db, user_id=int(other_id))

    rows = (
        db.execute(
            select(MatchMessage)
            .where(MatchMessage.match_id == match_id)
            .order_by(MatchMessage.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [
        MessageOut(
            id=row.id,
            conversation_id=match_id,
            sender_id=str(row.sender_id),
            body=row.body,
            client_message_id=row.client_message_id,
            created_at=_dt_z(row.created_at),
            read_at=_dt_z(row.read_at) if row.read_at else None,
        )
        for row in rows
    ]


@router.post("/{match_id}/messages", response_model=MessageOut)
async def post_message(
    request: Request,
    payload: MessageIn,
    user: CurrentUser,
    db: SessionDep,
    match_id: str = Path(..., min_length=1, max_length=128),
) -> MessageOut:
    match = _require_match(db=db, match_id=match_id, user_id=int(user.id))
    if match.status != "connected":
        raise APIError(code="MATCH_NOT_CONNECTED", message="只有 connected 才能发消息", status_code=403)

    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    _require_conversation_consent(db=db, user_id=int(user.id))
    _require_conversation_consent(db=db, user_id=int(other_id))

    existing = (
        db.execute(
            select(MatchMessage).where(
                and_(
                    MatchMessage.match_id == match_id,
                    MatchMessage.sender_id == user.id,
                    MatchMessage.client_message_id == payload.client_message_id,
                )
            )
        )
        .scalars()
        .one_or_none()
    )
    if existing is not None:
        return MessageOut(
            id=existing.id,
            conversation_id=match_id,
            sender_id=str(existing.sender_id),
            body=existing.body,
            client_message_id=existing.client_message_id,
            created_at=_dt_z(existing.created_at),
            read_at=_dt_z(existing.read_at) if existing.read_at else None,
        )

    msg = MatchMessage(
        id=new_id(),
        match_id=match_id,
        sender_id=int(user.id),
        body=payload.body,
        client_message_id=payload.client_message_id,
        read_at=None,
    )
    db.add(msg)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(code="IDEMPOTENCY_CONFLICT", message="client_message_id 冲突", status_code=409)
    db.refresh(msg)

    if request is not None:
        hub = getattr(request.app.state, "match_hub", None)
        if hub is not None:
            await hub.broadcast(
                match_id, {"type": "message.created", "data": {"id": msg.id, "body": msg.body}}
            )

    return MessageOut(
        id=msg.id,
        conversation_id=match_id,
        sender_id=str(msg.sender_id),
        body=msg.body,
        client_message_id=msg.client_message_id,
        created_at=_dt_z(msg.created_at),
        read_at=None,
    )
