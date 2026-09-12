from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import AuditLog, IdempotencyKey
from app.security import stable_hash


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def record_audit(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata_safe: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_safe=metadata_safe or {},
    )
    db.add(entry)
    return entry


def execute_idempotent(
    db: Session,
    *,
    user_id: str,
    scope: str,
    key: str | None,
    request_payload: Any,
    operation: Callable[[], Any],
) -> Any:
    if not key:
        return operation()
    request_hash = stable_hash(repr(request_payload))
    existing = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.scope == scope,
            IdempotencyKey.key == key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键不能用于不同请求",
                status_code=409,
            )
        return existing.response
    result = operation()
    db.add(
        IdempotencyKey(
            user_id=user_id,
            scope=scope,
            key=key,
            request_hash=request_hash,
            response=_serialize(result),
        )
    )
    db.commit()
    return result
