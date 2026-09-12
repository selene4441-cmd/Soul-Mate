from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Block,
    Claim,
    ConnectionRequest,
    Consent,
    Conversation,
    ConversationCue,
    ConversationMember,
    DeletionRequest,
    Evidence,
    FeatureSnapshot,
    IdempotencyKey,
    Impression,
    Match,
    Message,
    Notification,
    Outcome,
    PairFeature,
    RawDocument,
    SafetyEvent,
    User,
    UserAction,
    UserSession,
)
from app.modules.audit import record_audit


def delete_user_data(db: Session, user: User) -> DeletionRequest:
    request = DeletionRequest(user_id=user.id, status="processing")
    db.add(request)
    db.flush()

    match_ids = list(
        db.scalars(
            select(Match.id).where(or_(Match.user_a_id == user.id, Match.user_b_id == user.id))
        ).all()
    )
    conversation_ids: list[str] = []
    if match_ids:
        conversation_ids = list(
            db.scalars(select(Conversation.id).where(Conversation.match_id.in_(match_ids))).all()
        )
    if conversation_ids:
        db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
        db.execute(
            delete(ConversationCue).where(ConversationCue.conversation_id.in_(conversation_ids))
        )
        db.execute(
            delete(ConversationMember).where(
                ConversationMember.conversation_id.in_(conversation_ids)
            )
        )
        db.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))

    db.execute(
        delete(ConnectionRequest).where(
            or_(
                ConnectionRequest.requester_id == user.id,
                ConnectionRequest.recipient_id == user.id,
            )
        )
    )
    db.execute(delete(Block).where(Block.blocker_id == user.id))
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(Outcome).where(Outcome.user_id == user.id))
    db.execute(delete(SafetyEvent).where(SafetyEvent.reporter_id == user.id))
    if match_ids:
        db.execute(delete(Match).where(Match.id.in_(match_ids)))
    db.execute(
        delete(PairFeature).where(
            or_(PairFeature.user_a_id == user.id, PairFeature.user_b_id == user.id)
        )
    )
    db.execute(
        delete(Impression).where(
            or_(Impression.user_id == user.id, Impression.candidate_id == user.id)
        )
    )
    db.execute(
        delete(UserAction).where(
            or_(UserAction.user_id == user.id, UserAction.candidate_id == user.id)
        )
    )
    db.execute(delete(FeatureSnapshot).where(FeatureSnapshot.user_id == user.id))
    db.execute(delete(Claim).where(Claim.user_id == user.id))
    db.execute(delete(Evidence).where(Evidence.user_id == user.id))
    db.execute(delete(RawDocument).where(RawDocument.user_id == user.id))
    db.execute(delete(Consent).where(Consent.user_id == user.id))
    db.execute(delete(IdempotencyKey).where(IdempotencyKey.user_id == user.id))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))

    original_id = user.id
    user.email = f"deleted-{original_id}@invalid.local"
    user.display_name = "已删除用户"
    user.password_hash = "deleted"
    user.status = "deleted"
    user.deleted_at = datetime.now(timezone.utc)
    user.role = "user"

    record_audit(
        db,
        actor_id=None,
        action="privacy.deletion_completed",
        entity_type="user",
        entity_id=original_id,
        metadata_safe={"derived_records_removed": True, "raw_content_removed": True},
    )
    request.status = "completed"
    request.completed_at = datetime.now(timezone.utc)
    request.audit_tombstone = {
        "user_id": original_id,
        "completed_at": request.completed_at.isoformat(),
        "contains_content": False,
    }
    db.commit()
    db.refresh(request)
    return request
