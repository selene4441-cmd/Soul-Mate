from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import BehaviorEventType, ElicitationKind


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    behavior_events: Mapped[list[BehaviorEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    responses: Mapped[list[Response]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped[Profile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    beliefs: Mapped[list[Belief]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class BehaviorEvent(Base):
    __tablename__ = "behavior_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[BehaviorEventType] = mapped_column(
        Enum(BehaviorEventType, native_enum=False), nullable=False
    )
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user: Mapped[User] = relationship(back_populates="behavior_events")


class Elicitation(Base):
    __tablename__ = "elicitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    kind: Mapped[ElicitationKind] = mapped_column(
        Enum(ElicitationKind, native_enum=False), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    responses: Mapped[list[Response]] = relationship(
        back_populates="elicitation", cascade="all, delete-orphan"
    )


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    elicitation_id: Mapped[int] = mapped_column(
        ForeignKey("elicitations.id"), nullable=False, index=True
    )
    choice: Mapped[str] = mapped_column(Text, nullable=False)
    reaction_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="responses")
    elicitation: Mapped[Elicitation] = relationship(back_populates="responses")


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Belief(Base):
    __tablename__ = "beliefs"
    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_beliefs_confidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="beliefs")


class MatchCache(Base):
    __tablename__ = "match_cache"

    user_id_a: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    user_id_b: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    profile_hash_a: Mapped[str] = mapped_column(Text, nullable=False)
    profile_hash_b: Mapped[str] = mapped_column(Text, nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    entropy: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    narrative: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_a: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user_b: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    beta: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    signals: Mapped[list[RelationshipSignal]] = relationship(
        back_populates="relationship", cascade="all, delete-orphan"
    )


class RelationshipSignal(Base):
    __tablename__ = "relationship_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relationship_id: Mapped[int] = mapped_column(
        ForeignKey("relationships.id"), nullable=False, index=True
    )

    source: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    relationship: Mapped[Relationship] = relationship(back_populates="signals")
