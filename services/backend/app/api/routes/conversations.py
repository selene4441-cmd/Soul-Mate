from typing import Annotated

from fastapi import APIRouter, Header, Query

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.conversations import (
    close_conversation,
    conversation_for_user,
    list_conversations,
    mark_read,
    serialize_conversation,
)
from app.modules.messages import list_messages_page, send_message
from app.schemas import (
    ConversationCloseRequest,
    ConversationResponse,
    MessageCreate,
    MessagePage,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
def get_conversations(user: CurrentUser, db: DbSession) -> list[ConversationResponse]:
    return list_conversations(db, user)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    user: CurrentUser,
    db: DbSession,
) -> ConversationResponse:
    return serialize_conversation(db, conversation_for_user(db, user, conversation_id), user)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
def get_messages(
    conversation_id: str,
    user: CurrentUser,
    db: DbSession,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> MessagePage:
    return list_messages_page(db, user, conversation_id, cursor=cursor, limit=limit)


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
def create_message(
    conversation_id: str,
    payload: MessageCreate,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MessageResponse:
    if idempotency_key:
        payload = payload.model_copy(update={"client_message_id": idempotency_key})
    return send_message(db, user, conversation_id, payload)


@router.post("/{conversation_id}/close", response_model=ConversationResponse)
def close(
    conversation_id: str,
    payload: ConversationCloseRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> ConversationResponse:
    return close_conversation(db, user, conversation_id)


@router.post("/{conversation_id}/read", status_code=204)
def read_messages(
    conversation_id: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> None:
    mark_read(db, user, conversation_id)
