from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.ratelimit import RateLimit, RateLimiter
from app.models import BehaviorEvent, BehaviorEventType, User


router = APIRouter()

POST_EVENTS_LIMIT = RateLimit(limit=30, window_s=60)
GET_EVENTS_LIMIT = RateLimit(limit=120, window_s=60)


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        limiter = RateLimiter()
        request.app.state.rate_limiter = limiter
    return limiter


def _client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return host


def enforce_rate_limit(rule: RateLimit):
    def _dep(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> None:
        key = f"{request.url.path}:{_client_key(request)}"
        if not limiter.allow(key=key, rule=rule):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limited")

    return _dep


class EventIn(BaseModel):
    user_id: int = Field(..., ge=1)
    event_type: BehaviorEventType
    target_id: str | None = Field(default=None, max_length=128)
    duration_ms: int = Field(..., ge=0, le=300_000)


class EventsIn(BaseModel):
    events: list[EventIn] = Field(..., min_length=1, max_length=1000)


class EventsOut(BaseModel):
    inserted: int


class EventOut(BaseModel):
    id: int
    event_type: BehaviorEventType
    target_id: str | None
    duration_ms: int | None
    created_at: datetime


class UserEventsOut(BaseModel):
    items: list[EventOut]


@router.post(
    "/events",
    response_model=EventsOut,
    dependencies=[Depends(enforce_rate_limit(POST_EVENTS_LIMIT))],
)
def post_events(payload: EventsIn, session: Session = Depends(get_session)) -> EventsOut:
    user_ids = sorted({e.user_id for e in payload.events})
    users = session.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
    found = {u.id: u for u in users}

    missing = [uid for uid in user_ids if uid not in found]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"missing_user_ids": missing})

    no_consent = [uid for uid in user_ids if not found[uid].consent]
    if no_consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"no_consent_user_ids": no_consent})

    events = [
        BehaviorEvent(
            user_id=e.user_id,
            event_type=e.event_type,
            target_id=e.target_id,
            duration_ms=e.duration_ms,
        )
        for e in payload.events
    ]
    session.add_all(events)
    session.commit()
    return EventsOut(inserted=len(events))


@router.get(
    "/users/{user_id}/events",
    response_model=UserEventsOut,
    dependencies=[Depends(enforce_rate_limit(GET_EVENTS_LIMIT))],
)
def get_user_events(
    user_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> UserEventsOut:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    if not user.consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_consent")

    rows = (
        session.execute(
            select(BehaviorEvent)
            .where(BehaviorEvent.user_id == user_id)
            .order_by(BehaviorEvent.created_at.desc(), BehaviorEvent.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return UserEventsOut(
        items=[
            EventOut(
                id=row.id,
                event_type=row.event_type,
                target_id=row.target_id,
                duration_ms=row.duration_ms,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )
