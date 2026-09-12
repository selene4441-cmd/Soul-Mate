from typing import Annotated

from fastapi import APIRouter, Header

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.audit import execute_idempotent
from app.modules.interaction import get_messages, invite, list_matches, send_message
from app.schemas import (
    ConnectionRequestResponse,
    InvitationRequest,
    MatchResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(tags=["interaction"])


@router.post("/invitations", response_model=ConnectionRequestResponse, deprecated=True)
def create_invitation(
    payload: InvitationRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConnectionRequestResponse:
    return execute_idempotent(
        db,
        user_id=user.id,
        scope="invitation.create",
        key=idempotency_key,
        request_payload=payload.model_dump(),
        operation=lambda: invite(db, user, payload),
    )


@router.get("/matches", response_model=list[MatchResponse], deprecated=True)
def matches(user: CurrentUser, db: DbSession) -> list[MatchResponse]:
    return list_matches(db, user)


@router.get(
    "/matches/{match_id}/messages",
    response_model=list[MessageResponse],
    deprecated=True,
)
def messages(match_id: str, user: CurrentUser, db: DbSession) -> list[MessageResponse]:
    return get_messages(db, user, match_id)


@router.post(
    "/matches/{match_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    deprecated=True,
)
def create_message(
    match_id: str,
    payload: MessageCreate,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> MessageResponse:
    return send_message(db, user, match_id, payload)
