from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", name="uq_consents_user_scope"),
        Index("ix_consents_active", "scope", "revoked_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (Index("ix_claims_user_dimension", "user_id", "dimension"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(Text, nullable=False, default="preference")
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sensitivity: Mapped[str] = mapped_column(Text, nullable=False, default="L1")
    user_editable: Mapped[bool] = mapped_column(nullable=False, default=True)
    user_confirmed: Mapped[bool] = mapped_column(nullable=False, default=True)
    correction_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class RecommendationSession(Base):
    __tablename__ = "recommendation_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"
    __table_args__ = (
        UniqueConstraint("session_id", "candidate_id", name="uq_reco_item_session_candidate"),
        Index("ix_reco_items_user_candidate", "user_id", "candidate_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_sessions.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    common_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    differences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unknowns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    how_to_continue: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", name="uq_invitations_from_to"),
        Index("ix_invitations_pair", "from_user_id", "to_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id", name="uq_matches_pair"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchMessage(Base):
    __tablename__ = "match_messages"
    __table_args__ = (
        UniqueConstraint(
            "match_id", "sender_id", "client_message_id", name="uq_match_messages_idempotent"
        ),
        Index("ix_match_messages_match_created", "match_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    client_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

