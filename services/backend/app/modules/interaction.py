from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.dependencies import has_active_consent
from app.errors import DomainError
from app.models import Conversation, Match, Message, OutboxEvent, User
from app.modules.matching import get_candidate_lead
from app.schemas import InvitationRequest, MatchResponse, MessageCreate, MessageResponse


def _member_ids(match: Match) -> set[str]:
    return {match.user_a_id, match.user_b_id}


def _match_for_user(db: Session, user: User, match_id: str) -> Match:
    match = db.scalar(
        select(Match).where(
            Match.id == match_id,
            or_(Match.user_a_id == user.id, Match.user_b_id == user.id),
        )
    )
    if not match:
        raise DomainError("MATCH_NOT_FOUND", "未找到该关系连接", status_code=404)
    return match


def invite(
    db: Session,
    user: User,
    payload: InvitationRequest,
) -> MatchResponse:
    if not has_active_consent(db, user.id, "conversation:v1"):
        raise DomainError(
            "CONSENT_REQUIRED",
            "需要先授权对话用途",
            status_code=403,
            details={"scope": "conversation:v1"},
        )
    candidate = db.get(User, payload.candidate_id)
    if not candidate or candidate.status != "active" or not candidate.is_seed:
        raise DomainError("CANDIDATE_NOT_FOUND", "未找到该候选人", status_code=404)
    if not has_active_consent(db, candidate.id, "conversation:v1"):
        raise DomainError("CANDIDATE_UNAVAILABLE", "该候选人暂未授权交流", status_code=409)
    get_candidate_lead(db, user, candidate.id)

    pair_filter = or_(
        and_(Match.user_a_id == user.id, Match.user_b_id == candidate.id),
        and_(Match.user_a_id == candidate.id, Match.user_b_id == user.id),
    )
    match = db.scalar(select(Match).where(pair_filter))
    if match:
        return _serialize_match(db, user, match)

    match = Match(
        user_a_id=user.id,
        user_b_id=candidate.id,
        invited_by=user.id,
        status="connected" if candidate.is_seed else "invited",
    )
    db.add(match)
    db.flush()
    db.add(
        OutboxEvent(
            topic="match.invited",
            payload={
                "match_id": match.id,
                "inviter_id": user.id,
                "candidate_id": candidate.id,
                "has_message": payload.message is not None,
            },
        )
    )
    if match.status == "connected":
        db.add(Conversation(match_id=match.id))
    db.commit()
    db.refresh(match)
    return _serialize_match(db, user, match)


def list_matches(db: Session, user: User) -> list[MatchResponse]:
    rows = db.scalars(
        select(Match)
        .where(or_(Match.user_a_id == user.id, Match.user_b_id == user.id))
        .order_by(Match.updated_at.desc())
    ).all()
    return [_serialize_match(db, user, row) for row in rows]


def _serialize_match(db: Session, user: User, match: Match) -> MatchResponse:
    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    other = db.get(User, other_id)
    if not other or other.status != "active":
        raise DomainError("CANDIDATE_UNAVAILABLE", "该用户当前不可用", status_code=404)
    return MatchResponse(
        id=match.id,
        other_user={"id": other.id, "display_name": other.display_name},
        status=match.status,
        created_at=match.created_at,
    )


def _conversation_for_user(db: Session, user: User, match_id: str) -> Conversation:
    match = _match_for_user(db, user, match_id)
    if match.status != "connected":
        raise DomainError("CONVERSATION_NOT_OPEN", "对话尚未开放", status_code=409)
    conversation = db.scalar(select(Conversation).where(Conversation.match_id == match.id))
    if not conversation:
        conversation = Conversation(match_id=match.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def list_messages(db: Session, user: User, match_id: str) -> list[MessageResponse]:
    conversation = _conversation_for_user(db, user, match_id)
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(200)
    ).all()
    return [MessageResponse.model_validate(row) for row in rows]


def send_message(
    db: Session,
    user: User,
    match_id: str,
    payload: MessageCreate,
) -> MessageResponse:
    if not has_active_consent(db, user.id, "conversation:v1"):
        raise DomainError("CONSENT_REQUIRED", "需要先授权对话用途", status_code=403)
    conversation = _conversation_for_user(db, user, match_id)
    existing = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.client_message_id == payload.client_message_id,
        )
    )
    if existing:
        return MessageResponse.model_validate(existing)
    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        body=payload.body.strip(),
        client_message_id=payload.client_message_id,
    )
    db.add(message)
    db.flush()
    db.add(
        OutboxEvent(
            topic="message.created",
            payload={
                "conversation_id": conversation.id,
                "message_id": message.id,
                "sender_id": user.id,
            },
        )
    )
    db.commit()
    db.refresh(message)
    return MessageResponse.model_validate(message)
