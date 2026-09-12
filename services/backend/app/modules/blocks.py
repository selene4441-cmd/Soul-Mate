from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import (
    Block,
    ConnectionRequest,
    Conversation,
    ConversationMember,
    Match,
    Notification,
    User,
)
from app.modules.audit import record_audit
from app.modules.outbox import emit_event
from app.modules.relationships import relationship_pair_key
from app.schemas import BlockCreate, BlockResponse


def _serialize_block(db: Session, block: Block) -> BlockResponse:
    blocked = db.get(User, block.blocked_id)
    return BlockResponse(
        id=block.id,
        blocked_user={
            "id": block.blocked_id,
            "display_name": blocked.display_name if blocked else "不可用用户",
        },
        created_at=block.created_at,
        revoked_at=block.revoked_at,
    )


def create_block(db: Session, user: User, payload: BlockCreate) -> BlockResponse:
    if payload.blocked_user_id == user.id:
        raise DomainError("INVALID_BLOCK", "不能拉黑本人", status_code=422)
    blocked = db.get(User, payload.blocked_user_id)
    if not blocked or blocked.status != "active":
        raise DomainError("USER_NOT_FOUND", "未找到相关用户", status_code=404)

    existing = db.scalar(
        select(Block).where(
            Block.blocker_id == user.id,
            Block.blocked_id == blocked.id,
            Block.revoked_at.is_(None),
        )
    )
    if existing:
        return _serialize_block(db, existing)

    now = datetime.now(timezone.utc)
    block = Block(
        blocker_id=user.id,
        blocked_id=blocked.id,
        pair_key=relationship_pair_key(user.id, blocked.id),
        reason_private=payload.reason_private,
    )
    db.add(block)

    pending_requests = db.scalars(
        select(ConnectionRequest).where(
            ConnectionRequest.status == "pending",
            or_(
                and_(
                    ConnectionRequest.requester_id == user.id,
                    ConnectionRequest.recipient_id == blocked.id,
                ),
                and_(
                    ConnectionRequest.requester_id == blocked.id,
                    ConnectionRequest.recipient_id == user.id,
                ),
            ),
        )
    ).all()
    for request in pending_requests:
        request.status = "cancelled"
        request.responded_at = now

    match = db.scalar(
        select(Match).where(Match.pair_key == relationship_pair_key(user.id, blocked.id))
    )
    if match:
        match.status = "blocked"
        match.closed_at = now
        match.closed_by = user.id
        match.close_reason = "blocked"
        conversations = db.scalars(
            select(Conversation).where(Conversation.match_id == match.id)
        ).all()
        for conversation in conversations:
            conversation.status = "blocked"
            conversation.closed_at = now
            members = db.scalars(
                select(ConversationMember).where(
                    ConversationMember.conversation_id == conversation.id
                )
            ).all()
            for member in members:
                member.blocked_at = now
                member.exited_at = member.exited_at or now
            db.query(Notification).filter(
                Notification.entity_type == "conversation",
                Notification.entity_id == conversation.id,
                Notification.state == "pending",
            ).update({"state": "cancelled"})

    record_audit(
        db,
        actor_id=user.id,
        action="safety.blocked",
        entity_type="user",
        entity_id=blocked.id,
        metadata_safe={"block_id": block.id},
    )
    emit_event(
        db,
        topic="user.blocked",
        payload={"blocker_id": user.id, "blocked_id": blocked.id, "block_id": block.id},
    )
    db.commit()
    db.refresh(block)
    return _serialize_block(db, block)


def list_blocks(db: Session, user: User) -> list[BlockResponse]:
    rows = db.scalars(
        select(Block)
        .where(Block.blocker_id == user.id, Block.revoked_at.is_(None))
        .order_by(Block.created_at.desc())
    ).all()
    return [_serialize_block(db, row) for row in rows]


def revoke_block(db: Session, user: User, blocked_user_id: str) -> None:
    block = db.scalar(
        select(Block).where(
            Block.blocker_id == user.id,
            Block.blocked_id == blocked_user_id,
            Block.revoked_at.is_(None),
        )
    )
    if not block:
        raise DomainError("BLOCK_NOT_FOUND", "未找到有效拉黑记录", status_code=404)
    block.revoked_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor_id=user.id,
        action="safety.block_revoked",
        entity_type="user",
        entity_id=blocked_user_id,
        metadata_safe={"block_id": block.id},
    )
    db.commit()
