from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import DomainError
from app.models import Consent, Conversation, ConversationMember, Match, User
from app.modules.audit import record_audit
from app.modules.outbox import emit_event
from app.schemas import ConsentRequest, ConsentResponse

ALLOWED_SCOPES = {"matching:v1", "conversation:v1", "outcomes:v1"}


def grant_consent(db: Session, user: User, payload: ConsentRequest) -> ConsentResponse:
    if payload.scope not in ALLOWED_SCOPES:
        raise DomainError("CONSENT_SCOPE_INVALID", "不支持的授权范围")
    settings = get_settings()
    consent = db.scalar(
        select(Consent).where(
            Consent.user_id == user.id,
            Consent.scope == payload.scope,
            Consent.version == settings.consent_version,
        )
    )
    if consent:
        consent.purpose = payload.purpose
        consent.revoked_at = None
        consent.granted_at = datetime.now(timezone.utc)
    else:
        consent = Consent(
            user_id=user.id,
            scope=payload.scope,
            version=settings.consent_version,
            purpose=payload.purpose,
        )
        db.add(consent)
    record_audit(
        db,
        actor_id=user.id,
        action="consent.granted",
        entity_type="consent",
        entity_id=payload.scope,
        metadata_safe={"version": settings.consent_version},
    )
    db.commit()
    db.refresh(consent)
    return ConsentResponse.model_validate(consent)


def list_consents(db: Session, user: User) -> list[ConsentResponse]:
    settings = get_settings()
    rows = db.scalars(
        select(Consent)
        .where(Consent.user_id == user.id, Consent.version == settings.consent_version)
        .order_by(Consent.granted_at.asc())
    ).all()
    return [ConsentResponse.model_validate(row) for row in rows]


def revoke_consent(db: Session, user: User, scope: str) -> ConsentResponse:
    consent = db.scalar(
        select(Consent)
        .where(
            Consent.user_id == user.id,
            Consent.scope == scope,
            Consent.revoked_at.is_(None),
        )
        .order_by(Consent.granted_at.desc())
    )
    if not consent:
        raise DomainError("CONSENT_NOT_FOUND", "未找到有效授权", status_code=404)
    now = datetime.now(timezone.utc)
    consent.revoked_at = now
    if scope == "conversation:v1":
        memberships = db.scalars(
            select(ConversationMember).where(ConversationMember.user_id == user.id)
        ).all()
        for membership in memberships:
            conversation = db.get(Conversation, membership.conversation_id)
            if not conversation or conversation.status != "active":
                continue
            conversation.status = "closed"
            conversation.closed_at = now
            match = db.get(Match, conversation.match_id)
            if match and match.status == "active":
                match.status = "closed"
                match.closed_at = now
                match.closed_by = user.id
                match.close_reason = "consent_revoked"
            for member in db.scalars(
                select(ConversationMember).where(
                    ConversationMember.conversation_id == conversation.id
                )
            ).all():
                member.exited_at = member.exited_at or now
            emit_event(
                db,
                topic="conversation.closed",
                payload={
                    "conversation_id": conversation.id,
                    "closed_by": user.id,
                    "reason": "consent_revoked",
                },
            )
    record_audit(
        db,
        actor_id=user.id,
        action="consent.revoked",
        entity_type="consent",
        entity_id=scope,
    )
    db.commit()
    db.refresh(consent)
    return ConsentResponse.model_validate(consent)
