from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Notification, User
from app.schemas import NotificationResponse


def create_notification(
    db: Session,
    *,
    user_id: str,
    kind: str,
    entity_type: str,
    entity_id: str,
    dedupe_key: str,
) -> Notification | None:
    existing = db.scalar(select(Notification).where(Notification.dedupe_key == dedupe_key))
    if existing:
        return existing
    notification = Notification(
        user_id=user_id,
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        dedupe_key=dedupe_key,
    )
    db.add(notification)
    return notification


def list_notifications(db: Session, user: User) -> list[NotificationResponse]:
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
    ).all()
    return [NotificationResponse.model_validate(row) for row in rows]


def mark_notification_read(db: Session, user: User, notification_id: str) -> NotificationResponse:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    if not notification:
        raise DomainError("NOTIFICATION_NOT_FOUND", "未找到该通知", status_code=404)
    notification.read_at = datetime.now(timezone.utc)
    notification.state = "read"
    db.commit()
    db.refresh(notification)
    return NotificationResponse.model_validate(notification)
