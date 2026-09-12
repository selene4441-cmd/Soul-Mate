from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agents.relationship_store import (
    load_relationship_posterior,
    update_relationship_from_signals,
)
from app.api.events import SessionDep, enforce_rate_limit
from app.core.belief import entropy
from app.core.ratelimit import RateLimit
from app.models import Relationship, RelationshipSignal, User

router = APIRouter(prefix="/relationships", tags=["relationships"])

# Writing signals is cheap but still should be rate-limited to prevent spam.
SIGNALS_LIMIT = RateLimit(limit=3, window_s=60)

SignalKind = Literal[
    "message_tone",
    "response_latency",
    "shared_topic",
    "conflict",
    "repair",
]


class RelationshipSignalIn(BaseModel):
    source: str = Field(default="user", max_length=64)
    kind: SignalKind
    content: str = Field(default="", max_length=2000)
    weight: float = Field(default=1.0, ge=-10.0, le=10.0)


class RelationshipPosteriorOut(BaseModel):
    relationship_id: int
    user_a: int
    user_b: int
    alpha: float
    beta: float
    mean: float
    entropy: float


def _require_users_consented(session: SessionDep, user_ids: list[int]) -> None:
    rows = session.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
    found = {u.id: u for u in rows}
    missing = [uid for uid in user_ids if uid not in found]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"missing_user_ids": missing})
    no_consent = [uid for uid in user_ids if not found[uid].consent]
    if no_consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"no_consent_user_ids": no_consent})


@router.post(
    "/{user_a}/{user_b}/signals",
    response_model=RelationshipPosteriorOut,
    dependencies=[Depends(enforce_rate_limit(SIGNALS_LIMIT))],
)
def post_relationship_signal(
    payload: RelationshipSignalIn,
    request: Request,
    session: SessionDep,
    user_a: int = Path(..., ge=1),
    user_b: int = Path(..., ge=1),
) -> RelationshipPosteriorOut:
    if user_a == user_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="same_user")

    pair = sorted([int(user_a), int(user_b)])
    a0, b0 = pair[0], pair[1]
    _require_users_consented(session, [a0, b0])

    rel = session.execute(
        select(Relationship).where(Relationship.user_a == a0, Relationship.user_b == b0)
    ).scalar_one_or_none()
    if rel is None:
        rel = Relationship(user_a=a0, user_b=b0, status="unknown", alpha=1.0, beta=1.0, summary="")
        session.add(rel)
        session.flush()

    session.add(
        RelationshipSignal(
            relationship_id=rel.id,
            source=payload.source,
            kind=payload.kind,
            content=payload.content,
            weight=float(payload.weight),
        )
    )
    session.commit()

    rel2 = update_relationship_from_signals(session, relationship_id=rel.id)
    posterior = load_relationship_posterior(session, relationship_id=rel.id)

    return RelationshipPosteriorOut(
        relationship_id=int(rel2.id),
        user_a=int(rel2.user_a),
        user_b=int(rel2.user_b),
        alpha=float(posterior.alpha),
        beta=float(posterior.beta),
        mean=float(posterior.mean),
        entropy=float(entropy(posterior.mean)),
    )

