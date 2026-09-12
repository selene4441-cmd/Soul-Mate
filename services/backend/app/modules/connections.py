from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import has_active_consent
from app.errors import DomainError
from app.models import ConnectionRequest, User
from app.modules.audit import record_audit
from app.modules.conversations import open_conversation, serialize_conversation
from app.modules.cues import context_from_lead, default_topic, suggest_cues
from app.modules.matching import get_candidate_lead
from app.modules.notifications import create_notification
from app.modules.outbox import emit_event, publish_event
from app.modules.relationships import find_match, has_active_block, relationship_pair_key
from app.schemas import (
    ConnectionDecisionRequest,
    ConnectionRequestCreate,
    ConnectionRequestResponse,
    ConversationResponse,
    CueOption,
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _other_user(db: Session, request: ConnectionRequest, user: User) -> User:
    other_id = request.recipient_id if request.requester_id == user.id else request.requester_id
    other = db.get(User, other_id)
    if not other or other.status != "active":
        raise DomainError("USER_UNAVAILABLE", "相关用户当前不可用", status_code=404)
    return other


def _serialize_request(
    db: Session,
    request: ConnectionRequest,
    user: User,
) -> ConnectionRequestResponse:
    other = _other_user(db, request, user)
    return ConnectionRequestResponse(
        id=request.id,
        direction="outgoing" if request.requester_id == user.id else "incoming",
        other_user={"id": other.id, "display_name": other.display_name},
        status=request.status,
        cue_type=request.cue_type,
        topic_text=request.topic_text,
        personal_message=request.personal_message,
        context_snapshot=request.context_snapshot or {},
        recommendation_id=request.recommendation_id,
        expires_at=request.expires_at,
        responded_at=request.responded_at,
        created_at=request.created_at,
    )


def list_connection_requests(
    db: Session,
    user: User,
    *,
    direction: str = "incoming",
    status: str | None = "pending",
) -> list[ConnectionRequestResponse]:
    if direction not in {"incoming", "outgoing"}:
        raise DomainError("DIRECTION_INVALID", "请求方向无效", status_code=422)
    participant_filter = (
        ConnectionRequest.recipient_id == user.id
        if direction == "incoming"
        else ConnectionRequest.requester_id == user.id
    )
    query = select(ConnectionRequest).where(participant_filter)
    if status:
        query = query.where(ConnectionRequest.status == status)
    rows = db.scalars(query.order_by(ConnectionRequest.created_at.desc())).all()
    return [_serialize_request(db, row, user) for row in rows]


def get_connection_request(
    db: Session,
    user: User,
    request_id: str,
) -> ConnectionRequestResponse:
    request = db.scalar(
        select(ConnectionRequest).where(
            ConnectionRequest.id == request_id,
            or_(
                ConnectionRequest.requester_id == user.id,
                ConnectionRequest.recipient_id == user.id,
            ),
        )
    )
    if not request:
        raise DomainError("CONNECTION_REQUEST_NOT_FOUND", "未找到该连接请求", status_code=404)
    return _serialize_request(db, request, user)

def connection_cues(db: Session, user: User, candidate_id: str) -> list[CueOption]:
    lead = get_candidate_lead(db, user, candidate_id)
    return suggest_cues(lead)


def create_connection_request(
    db: Session,
    user: User,
    payload: ConnectionRequestCreate,
) -> ConnectionRequestResponse:
    settings = get_settings()
    if not has_active_consent(db, user.id, "conversation:v1"):
        raise DomainError(
            "CONSENT_REQUIRED",
            "需要先授权对话用途",
            status_code=403,
            details={"scope": "conversation:v1"},
        )
    if payload.candidate_id == user.id:
        raise DomainError("INVALID_RECIPIENT", "不能向本人发起连接", status_code=422)
    candidate = db.get(User, payload.candidate_id)
    if not candidate or candidate.status != "active":
        raise DomainError("CANDIDATE_NOT_FOUND", "未找到该候选人", status_code=404)
    if not has_active_consent(db, candidate.id, "conversation:v1"):
        raise DomainError("CANDIDATE_UNAVAILABLE", "该用户暂未授权交流", status_code=409)
    if has_active_block(db, user.id, candidate.id):
        raise DomainError("BLOCKED_RELATIONSHIP", "当前关系不能发送连接请求", status_code=403)

    lead = get_candidate_lead(db, user, candidate.id)
    pair_key = relationship_pair_key(user.id, candidate.id)
    existing_match = find_match(db, user.id, candidate.id)
    if existing_match:
        raise DomainError("ALREADY_CONNECTED", "你们已经建立过关系连接", status_code=409)

    pending = db.scalar(
        select(ConnectionRequest).where(
            ConnectionRequest.pair_key == pair_key,
            ConnectionRequest.status == "pending",
        )
    )
    if pending:
        return _serialize_request(db, pending, user)

    cooldown_start = datetime.now(timezone.utc) - timedelta(
        days=settings.connection_request_cooldown_days
    )
    declined = db.scalar(
        select(ConnectionRequest)
        .where(
            ConnectionRequest.requester_id == user.id,
            ConnectionRequest.recipient_id == candidate.id,
            ConnectionRequest.status == "declined",
            ConnectionRequest.responded_at.is_not(None),
            ConnectionRequest.responded_at >= cooldown_start,
        )
        .order_by(ConnectionRequest.responded_at.desc())
    )
    if declined and settings.connection_request_cooldown_days > 0:
        raise DomainError(
            "CONNECTION_REQUEST_COOLDOWN",
            "对方暂不联系，请尊重当前边界",
            status_code=409,
        )

    cue_type = payload.cue_type
    topic_text = (payload.topic_text or "").strip()
    if not topic_text:
        cue_type, topic_text = default_topic(lead)
    context_snapshot = context_from_lead(lead)
    now = datetime.now(timezone.utc)
    request = ConnectionRequest(
        pair_key=pair_key,
        requester_id=user.id,
        recipient_id=candidate.id,
        recommendation_id=payload.recommendation_id or lead.recommendation_id,
        recommendation_session_id=payload.recommendation_session_id,
        source_feature_ids=lead.evidence_ids,
        source_versions={
            "model_version": settings.model_version,
            "policy_version": settings.policy_version,
        },
        cue_type=cue_type,
        topic_text=topic_text,
        personal_message=(payload.personal_message or "").strip() or None,
        context_snapshot=context_snapshot,
        status="pending",
        policy_version=settings.policy_version,
        expires_at=now + timedelta(days=settings.connection_request_ttl_days),
    )
    db.add(request)
    db.flush()
    create_notification(
        db,
        user_id=candidate.id,
        kind="connection_request",
        entity_type="connection_request",
        entity_id=request.id,
        dedupe_key=f"connection-request:{request.id}",
    )
    emit_event(
        db,
        topic="connection.requested",
        payload={
            "connection_request_id": request.id,
            "requester_id": user.id,
            "recipient_id": candidate.id,
        },
    )
    record_audit(
        db,
        actor_id=user.id,
        action="connection.requested",
        entity_type="connection_request",
        entity_id=request.id,
        metadata_safe={"cue_type": cue_type},
    )
    db.commit()
    db.refresh(request)
    return _serialize_request(db, request, user)

def _request_for_decision(
    db: Session,
    user: User,
    request_id: str,
) -> ConnectionRequest:
    request = db.scalar(
        select(ConnectionRequest)
        .where(ConnectionRequest.id == request_id)
        .with_for_update()
    )
    if not request or request.recipient_id != user.id:
        raise DomainError("CONNECTION_REQUEST_NOT_FOUND", "未找到该连接请求", status_code=404)
    if request.status != "pending":
        raise DomainError(
            "CONNECTION_REQUEST_ALREADY_RESOLVED",
            "该请求已经处理",
            status_code=409,
        )
    if _as_utc(request.expires_at) <= datetime.now(timezone.utc):
        request.status = "expired"
        request.responded_at = datetime.now(timezone.utc)
        db.commit()
        raise DomainError("CONNECTION_REQUEST_EXPIRED", "该请求已经过期", status_code=409)
    return request


def accept_connection_request(
    db: Session,
    user: User,
    request_id: str,
) -> ConversationResponse:
    request = _request_for_decision(db, user, request_id)
    if not has_active_consent(
        db, request.requester_id, "conversation:v1"
    ) or not has_active_consent(db, request.recipient_id, "conversation:v1"):
        raise DomainError("CONSENT_REVOKED", "双方对话授权已失效", status_code=409)
    if has_active_block(db, request.requester_id, request.recipient_id):
        raise DomainError("BLOCKED_RELATIONSHIP", "当前关系不能开启交流", status_code=409)

    request.status = "accepted"
    request.responded_at = datetime.now(timezone.utc)
    conversation = open_conversation(
        db,
        request,
        context_snapshot=request.context_snapshot or {},
    )
    create_notification(
        db,
        user_id=request.requester_id,
        kind="connection_accepted",
        entity_type="conversation",
        entity_id=conversation.id,
        dedupe_key=f"connection-accepted:{request.id}",
    )
    event = emit_event(
        db,
        topic="connection.accepted",
        payload={
            "connection_request_id": request.id,
            "requester_id": request.requester_id,
            "recipient_id": request.recipient_id,
            "conversation_id": conversation.id,
        },
    )
    record_audit(
        db,
        actor_id=user.id,
        action="connection.accepted",
        entity_type="connection_request",
        entity_id=request.id,
        metadata_safe={"conversation_id": conversation.id},
    )
    db.commit()
    db.refresh(conversation)
    publish_event(db, event)
    db.commit()
    return serialize_conversation(db, conversation, user)


def decline_connection_request(
    db: Session,
    user: User,
    request_id: str,
    payload: ConnectionDecisionRequest,
) -> ConnectionRequestResponse:
    request = _request_for_decision(db, user, request_id)
    request.status = "declined"
    request.responded_at = datetime.now(timezone.utc)
    request.decline_reason_private = (payload.reason_private or "").strip() or None
    emit_event(
        db,
        topic="connection.declined",
        payload={
            "connection_request_id": request.id,
            "requester_id": request.requester_id,
            "recipient_id": request.recipient_id,
        },
    )
    record_audit(
        db,
        actor_id=user.id,
        action="connection.declined",
        entity_type="connection_request",
        entity_id=request.id,
        metadata_safe={"reason_present": bool(request.decline_reason_private)},
    )
    db.commit()
    db.refresh(request)
    return _serialize_request(db, request, user)


def cancel_connection_request(db: Session, user: User, request_id: str) -> None:
    request = db.scalar(
        select(ConnectionRequest)
        .where(
            ConnectionRequest.id == request_id,
            ConnectionRequest.requester_id == user.id,
        )
        .with_for_update()
    )
    if not request:
        raise DomainError("CONNECTION_REQUEST_NOT_FOUND", "未找到该连接请求", status_code=404)
    if request.status != "pending":
        raise DomainError(
            "CONNECTION_REQUEST_ALREADY_RESOLVED",
            "该请求已经处理",
            status_code=409,
        )
    request.status = "cancelled"
    request.responded_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor_id=user.id,
        action="connection.cancelled",
        entity_type="connection_request",
        entity_id=request.id,
    )
    db.commit()


def expire_connection_requests(db: Session, *, limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(ConnectionRequest)
        .where(
            ConnectionRequest.status == "pending",
            ConnectionRequest.expires_at <= now,
        )
        .limit(limit)
    ).all()
    for request in rows:
        request.status = "expired"
        request.responded_at = now
    db.commit()
    return len(rows)
