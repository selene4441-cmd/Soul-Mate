from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import ConversationMember, Message, SafetyEvent, User
from app.modules.audit import record_audit
from app.schemas import AdminSafetyUpdate, SafetyEventResponse, SafetyReportCreate
from app.security import stable_hash


def report_safety_event(
    db: Session,
    reporter: User,
    payload: SafetyReportCreate,
) -> SafetyEventResponse:
    if payload.subject_id == reporter.id:
        raise DomainError("INVALID_SUBJECT", "不能将本人作为举报对象", status_code=422)
    subject = db.get(User, payload.subject_id)
    if not subject:
        raise DomainError("USER_NOT_FOUND", "未找到相关用户", status_code=404)
    if payload.conversation_id:
        membership = db.scalar(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == payload.conversation_id,
                ConversationMember.user_id == reporter.id,
            )
        )
        if not membership:
            raise DomainError("CONVERSATION_NOT_FOUND", "未找到该会话", status_code=404)
    if payload.message_id:
        message = db.get(Message, payload.message_id)
        if (
            not message
            or message.conversation_id != payload.conversation_id
            or not db.scalar(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == message.conversation_id,
                    ConversationMember.user_id == reporter.id,
                )
            )
        ):
            raise DomainError("MESSAGE_NOT_FOUND", "未找到相关消息", status_code=404)
    details_hash = stable_hash(payload.details) if payload.details else None
    details_reference = f"report-hash://{details_hash}" if details_hash else None
    event = SafetyEvent(
        reporter_id=reporter.id,
        subject_id=payload.subject_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        event_type=payload.event_type,
        severity=payload.severity,
        details_reference=details_reference,
        details_hash=details_hash,
    )
    db.add(event)
    db.flush()
    record_audit(
        db,
        actor_id=reporter.id,
        action="safety.reported",
        entity_type="safety_event",
        entity_id=event.id,
        metadata_safe={"event_type": payload.event_type, "severity": payload.severity},
    )
    db.commit()
    db.refresh(event)
    return SafetyEventResponse.model_validate(event)


def list_safety_events(db: Session, status: str | None = None) -> list[SafetyEventResponse]:
    query = select(SafetyEvent).order_by(SafetyEvent.created_at.desc())
    if status:
        query = query.where(SafetyEvent.status == status)
    return [SafetyEventResponse.model_validate(row) for row in db.scalars(query).all()]


def review_safety_event(
    db: Session,
    admin: User,
    event_id: str,
    payload: AdminSafetyUpdate,
) -> SafetyEventResponse:
    event = db.get(SafetyEvent, event_id)
    if not event:
        raise DomainError("SAFETY_EVENT_NOT_FOUND", "未找到安全事件", status_code=404)
    event.status = payload.status
    event.reviewer_id = admin.id
    event.reviewed_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor_id=admin.id,
        action="safety.reviewed",
        entity_type="safety_event",
        entity_id=event.id,
        metadata_safe={"status": payload.status, "note_present": bool(payload.review_note)},
    )
    db.commit()
    db.refresh(event)
    return SafetyEventResponse.model_validate(event)
