from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import SafetyEvent, User
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
    details_reference = None
    if payload.details:
        details_reference = f"report-hash://{stable_hash(payload.details)}"
    event = SafetyEvent(
        reporter_id=reporter.id,
        subject_id=payload.subject_id,
        event_type=payload.event_type,
        severity=payload.severity,
        details_reference=details_reference,
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
