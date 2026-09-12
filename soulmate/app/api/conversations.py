from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.events import SessionDep, enforce_rate_limit
from app.core.ratelimit import RateLimit
from app.models import Conversation, Message, User

router = APIRouter(prefix="/conversations", tags=["conversations"])

WRITE_LIMIT = RateLimit(limit=30, window_s=60)

REQUIRED_SCOPE = "conversation"


class MessageIn(BaseModel):
    sender_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1, max_length=4000)


class MessageOut(BaseModel):
    conversation_id: int
    message_id: int


def _require_user(session: SessionDep, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    return user


def _require_conversation_scope(*, user: User) -> None:
    scopes = user.consent_scopes or []
    if REQUIRED_SCOPE not in scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_conversation_consent")


@router.post(
    "/{user_a}/{user_b}/messages",
    response_model=MessageOut,
    dependencies=[Depends(enforce_rate_limit(WRITE_LIMIT))],
)
def post_message(
    payload: MessageIn,
    session: SessionDep,
    user_a: int = Path(..., ge=1),
    user_b: int = Path(..., ge=1),
) -> MessageOut:
    if user_a == user_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="same_user")

    a0, b0 = sorted([int(user_a), int(user_b)])
    if payload.sender_id not in {a0, b0}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sender_not_in_conversation")

    ua = _require_user(session, a0)
    ub = _require_user(session, b0)
    if not ua.consent or not ub.consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_consent")
    _require_conversation_scope(user=ua)
    _require_conversation_scope(user=ub)

    convo = session.execute(
        select(Conversation).where(Conversation.user_a == a0, Conversation.user_b == b0)
    ).scalar_one_or_none()
    if convo is None:
        convo = Conversation(user_a=a0, user_b=b0)
        session.add(convo)
        session.flush()

    msg = Message(conversation_id=convo.id, sender_id=payload.sender_id, content=payload.content)
    session.add(msg)
    session.commit()
    return MessageOut(conversation_id=int(convo.id), message_id=int(msg.id))

