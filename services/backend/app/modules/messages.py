from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.dependencies import has_active_consent
from app.errors import DomainError
from app.models import Conversation, ConversationMember, Match, Message, User
from app.modules.audit import record_audit
from app.modules.conversations import conversation_for_user
from app.modules.outbox import emit_event, publish_event
from app.modules.relationships import has_active_block
from app.schemas import MessageCreate, MessagePage, MessageResponse


def _member_ids(db: Session, conversation_id: str) -> set[str]:
    return set(
        db.scalars(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == conversation_id
            )
        ).all()
    )


def _assert_send_allowed(db: Session, user: User, conversation: Conversation) -> set[str]:
    if conversation.status != "active":
        raise DomainError("CONVERSATION_CLOSED", "该交流已经结束", status_code=409)
    member_ids = _member_ids(db, conversation.id)
    if user.id not in member_ids:
        raise DomainError("CONVERSATION_NOT_FOUND", "未找到该会话", status_code=404)
    for member_id in member_ids:
        if not has_active_consent(db, member_id, "conversation:v1"):
            raise DomainError(
                "CONSENT_REVOKED",
                "任一方撤回对话授权后不能继续发送消息",
                status_code=409,
                details={"user_id": member_id},
            )
    other_ids = member_ids - {user.id}
    if any(has_active_block(db, user.id, other_id) for other_id in other_ids):
        raise DomainError("BLOCKED_RELATIONSHIP", "当前关系已停止交流", status_code=409)
    return member_ids


def _encode_cursor(message: Message) -> str:
    value = json.dumps({"created_at": message.created_at.isoformat(), "id": message.id})
    return base64.urlsafe_b64encode(value.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        created_at = datetime.fromisoformat(payload["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at, str(payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DomainError("CURSOR_INVALID", "消息游标无效", status_code=422) from exc


def list_messages_page(
    db: Session,
    user: User,
    conversation_id: str,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> MessagePage:
    conversation = conversation_for_user(db, user, conversation_id)
    safe_limit = min(max(limit, 1), 100)
    query = select(Message).where(Message.conversation_id == conversation.id)
    if cursor:
        created_at, message_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                Message.created_at > created_at,
                and_(Message.created_at == created_at, Message.id > message_id),
            )
        )
    rows = db.scalars(
        query.order_by(Message.created_at.asc(), Message.id.asc()).limit(safe_limit + 1)
    ).all()
    has_more = len(rows) > safe_limit
    items = rows[:safe_limit]
    return MessagePage(
        items=[MessageResponse.model_validate(row) for row in items],
        next_cursor=_encode_cursor(items[-1]) if has_more and items else None,
    )


def list_messages(db: Session, user: User, match_id: str) -> list[MessageResponse]:
    match = db.scalar(
        select(Match).where(
            Match.id == match_id,
            or_(Match.user_a_id == user.id, Match.user_b_id == user.id),
        )
    )
    if not match:
        raise DomainError("MATCH_NOT_FOUND", "未找到该关系连接", status_code=404)
    conversation = db.scalar(select(Conversation).where(Conversation.match_id == match.id))
    if not conversation:
        raise DomainError("CONVERSATION_NOT_FOUND", "未找到该会话", status_code=404)
    return list_messages_page(db, user, conversation.id, limit=100).items


def send_message(
    db: Session,
    user: User,
    conversation_or_match_id: str,
    payload: MessageCreate,
    *,
    match_route: bool = False,
) -> MessageResponse:
    if match_route:
        match = db.scalar(
            select(Match).where(
                Match.id == conversation_or_match_id,
                or_(Match.user_a_id == user.id, Match.user_b_id == user.id),
            )
        )
        if not match:
            raise DomainError("MATCH_NOT_FOUND", "未找到该关系连接", status_code=404)
        conversation = db.scalar(
            select(Conversation).where(Conversation.match_id == match.id)
        )
        if not conversation:
            raise DomainError("CONVERSATION_NOT_FOUND", "未找到该会话", status_code=404)
    else:
        conversation = conversation_for_user(db, user, conversation_or_match_id)

    _assert_send_allowed(db, user, conversation)
    existing = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.client_message_id == payload.client_message_id,
        )
    )
    if existing:
        return MessageResponse.model_validate(existing)
    if payload.reply_to_id:
        reply = db.get(Message, payload.reply_to_id)
        if not reply or reply.conversation_id != conversation.id:
            raise DomainError("REPLY_NOT_FOUND", "回复的消息不存在", status_code=422)

    now = datetime.now(timezone.utc)
    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        body=payload.body,
        client_message_id=payload.client_message_id,
        kind=payload.kind,
        reply_to_id=payload.reply_to_id,
    )
    db.add(message)
    conversation.last_message_at = now
    db.flush()
    event = emit_event(
        db,
        topic="message.created",
        payload={
            "conversation_id": conversation.id,
            "message_id": message.id,
            "sender_id": user.id,
        },
    )
    record_audit(
        db,
        actor_id=user.id,
        action="message.created",
        entity_type="message",
        entity_id=message.id,
        metadata_safe={"conversation_id": conversation.id, "kind": payload.kind},
    )
    db.commit()
    db.refresh(message)
    publish_event(db, event)
    db.commit()
    return MessageResponse.model_validate(message)
