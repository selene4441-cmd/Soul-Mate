from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from redis import Redis
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import OutboxEvent, new_id


def emit_event(
    db: Session,
    *,
    topic: str,
    payload: dict[str, Any],
    event_key: str | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        event_key=event_key or new_id(),
        topic=topic,
        payload=payload,
    )
    db.add(event)
    return event


def _channels(topic: str, payload: dict[str, Any]) -> list[str]:
    channels: list[str] = []
    conversation_id = payload.get("conversation_id")
    recipient_id = payload.get("recipient_id")
    if conversation_id:
        channels.append(f"tongpin:conversation:{conversation_id}:events")
    if recipient_id:
        channels.append(f"tongpin:user:{recipient_id}:events")
    if not channels:
        channels.append("tongpin:events")
    return channels


def _envelope(event: OutboxEvent) -> dict[str, Any]:
    return {
        "channels": _channels(event.topic, event.payload),
        "event": {
            "type": event.topic,
            "event_id": event.id,
            "occurred_at": event.created_at.isoformat(),
            "data": event.payload,
        },
    }


def publish_event(db: Session, event: OutboxEvent) -> bool:
    settings = get_settings()
    if not settings.realtime_broker_enabled:
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        return True
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
            decode_responses=True,
        )
        client.publish("tongpin:events", json.dumps(_envelope(event), ensure_ascii=False))
        client.close()
    except Exception as exc:
        event.status = "pending"
        event.attempts += 1
        event.available_at = datetime.now(timezone.utc) + timedelta(seconds=min(2 ** event.attempts, 60))
        event.last_error = type(exc).__name__
        return False
    event.status = "processed"
    event.processed_at = datetime.now(timezone.utc)
    return True


def dispatch_pending_outbox(db: Session, *, limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    events = db.scalars(
        select(OutboxEvent)
        .where(
            or_(OutboxEvent.status == "pending", OutboxEvent.status == "retry"),
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
    ).all()
    processed = 0
    for event in events:
        if publish_event(db, event):
            processed += 1
    db.commit()
    return processed
