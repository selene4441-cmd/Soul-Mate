from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import (
    ConnectionRequest,
    Conversation,
    ConversationCue,
    ConversationMember,
    Match,
    Message,
    User,
)
from app.modules.audit import record_audit
from app.modules.outbox import emit_event
from app.modules.relationships import relationship_pair_key
from app.schemas import ConversationCueResponse, ConversationResponse


def open_conversation(
    db: Session,
    request: ConnectionRequest,
    *,
    context_snapshot: dict,
) -> Conversation:
    now = datetime.now(timezone.utc)
    match = Match(
        pair_key=relationship_pair_key(request.requester_id, request.recipient_id),
        user_a_id=request.requester_id,
        user_b_id=request.recipient_id,
        status="active",
        invited_by=request.requester_id,
        accepted_at=now,
    )
    db.add(match)
    db.flush()

    conversation = Conversation(
        match_id=match.id,
        status="active",
        context_snapshot=context_snapshot,
        opened_at=now,
    )
    db.add(conversation)
    db.flush()

    for user_id in (request.requester_id, request.recipient_id):
        db.add(ConversationMember(conversation_id=conversation.id, user_id=user_id))

    db.add(
        ConversationCue(
            conversation_id=conversation.id,
            connection_request_id=request.id,
            cue_type=request.cue_type,
            text=request.topic_text,
            source_feature_ids=request.source_feature_ids,
            source_versions=request.source_versions,
            created_by="system",
        )
    )
    return conversation


def conversation_for_user(db: Session, user: User, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(
            Conversation.id == conversation_id,
            ConversationMember.user_id == user.id,
        )
    )
    if not conversation:
        raise DomainError("CONVERSATION_NOT_FOUND", "未找到该会话", status_code=404)
    return conversation


def _other_user(db: Session, conversation: Conversation, user: User) -> User:
    match = db.get(Match, conversation.match_id)
    if not match:
        raise DomainError("CONVERSATION_NOT_FOUND", "未找到该会话", status_code=404)
    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    other = db.get(User, other_id)
    if not other or other.status != "active":
        raise DomainError("USER_UNAVAILABLE", "对方当前不可用", status_code=404)
    return other


def _active_cue(db: Session, conversation_id: str) -> ConversationCue | None:
    return db.scalar(
        select(ConversationCue)
        .where(
            ConversationCue.conversation_id == conversation_id,
            ConversationCue.status == "active",
        )
        .order_by(ConversationCue.created_at.asc())
    )


def _unread_count(db: Session, conversation_id: str, user: User) -> int:
    member = db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user.id,
        )
    )
    query = select(func.count(Message.id)).where(
        Message.conversation_id == conversation_id,
        Message.sender_id != user.id,
        Message.deleted_at.is_(None),
    )
    if member and member.last_read_at:
        query = query.where(Message.created_at > member.last_read_at)
    elif member:
        query = query.where(Message.read_at.is_(None))
    return int(db.scalar(query) or 0)


def serialize_conversation(
    db: Session,
    conversation: Conversation,
    user: User,
) -> ConversationResponse:
    other = _other_user(db, conversation, user)
    cue = _active_cue(db, conversation.id)
    return ConversationResponse(
        id=conversation.id,
        match_id=conversation.match_id,
        other_user={"id": other.id, "display_name": other.display_name},
        status=conversation.status,
        context_snapshot=conversation.context_snapshot or {},
        active_cue=ConversationCueResponse.model_validate(cue) if cue else None,
        opened_at=conversation.opened_at,
        last_message_at=conversation.last_message_at,
        unread_count=_unread_count(db, conversation.id, user),
        created_at=conversation.created_at,
    )


def list_conversations(db: Session, user: User) -> list[ConversationResponse]:
    rows = db.scalars(
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == user.id)
        .order_by(
            func.coalesce(Conversation.last_message_at, Conversation.opened_at).desc(),
        )
    ).all()
    return [serialize_conversation(db, row, user) for row in rows]


def close_conversation(db: Session, user: User, conversation_id: str) -> ConversationResponse:
    conversation = conversation_for_user(db, user, conversation_id)
    if conversation.status != "active":
        raise DomainError("CONVERSATION_CLOSED", "该交流已经结束", status_code=409)
    now = datetime.now(timezone.utc)
    conversation.status = "closed"
    conversation.closed_at = now
    match = db.get(Match, conversation.match_id)
    if match:
        match.status = "closed"
        match.closed_at = now
        match.closed_by = user.id
        match.close_reason = "user_closed"
    members = db.scalars(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id
        )
    ).all()
    for member in members:
        member.exited_at = now
    record_audit(
        db,
        actor_id=user.id,
        action="conversation.closed",
        entity_type="conversation",
        entity_id=conversation.id,
        metadata_safe={"reason": "user_closed"},
    )
    for member in members:
        if member.user_id != user.id:
            from app.modules.notifications import create_notification

            create_notification(
                db,
                user_id=member.user_id,
                kind="conversation_closed",
                entity_type="conversation",
                entity_id=conversation.id,
                dedupe_key=f"conversation-closed:{conversation.id}:{member.user_id}",
            )
    emit_event(
        db,
        topic="conversation.closed",
        payload={"conversation_id": conversation.id, "closed_by": user.id},
    )
    db.commit()
    db.refresh(conversation)
    return serialize_conversation(db, conversation, user)


def mark_read(db: Session, user: User, conversation_id: str) -> None:
    conversation = conversation_for_user(db, user, conversation_id)
    now = datetime.now(timezone.utc)
    member = db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id,
            ConversationMember.user_id == user.id,
        )
    )
    if member:
        member.last_read_at = now
    db.execute(
        Message.__table__.update()
        .where(
            Message.conversation_id == conversation.id,
            Message.sender_id != user.id,
            Message.read_at.is_(None),
        )
        .values(read_at=now)
    )
    db.commit()
