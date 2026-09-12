from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Match, User
from app.modules.connections import create_connection_request
from app.modules.messages import list_messages
from app.modules.messages import send_message as send_conversation_message
from app.schemas import (
    ConnectionRequestCreate,
    ConnectionRequestResponse,
    InvitationRequest,
    MatchResponse,
    MessageCreate,
    MessageResponse,
)


def invite(db: Session, user: User, payload: InvitationRequest) -> ConnectionRequestResponse:
    return create_connection_request(
        db,
        user,
        ConnectionRequestCreate(
            candidate_id=payload.candidate_id,
            personal_message=payload.message,
        ),
    )


def list_matches(db: Session, user: User) -> list[MatchResponse]:
    rows = db.scalars(
        select(Match)
        .where(
            or_(Match.user_a_id == user.id, Match.user_b_id == user.id),
            Match.status.in_(["active", "connected"]),
        )
        .order_by(Match.updated_at.desc())
    ).all()
    return [_serialize_match(db, user, row) for row in rows]


def _serialize_match(db: Session, user: User, match: Match) -> MatchResponse:
    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    other = db.get(User, other_id)
    if not other or other.status != "active":
        raise DomainError("USER_UNAVAILABLE", "相关用户当前不可用", status_code=404)
    return MatchResponse(
        id=match.id,
        other_user={"id": other.id, "display_name": other.display_name},
        status=match.status,
        created_at=match.created_at,
    )


def get_messages(db: Session, user: User, match_id: str) -> list[MessageResponse]:
    return list_messages(db, user, match_id)


def send_message(
    db: Session,
    user: User,
    match_id: str,
    payload: MessageCreate,
) -> MessageResponse:
    return send_conversation_message(db, user, match_id, payload, match_route=True)
