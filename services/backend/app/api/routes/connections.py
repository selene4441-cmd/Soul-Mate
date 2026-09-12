from typing import Annotated

from fastapi import APIRouter, Header, Query

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.audit import execute_idempotent
from app.modules.connections import (
    accept_connection_request,
    cancel_connection_request,
    create_connection_request,
    decline_connection_request,
    get_connection_request,
    list_connection_requests,
)
from app.schemas import (
    ConnectionDecisionRequest,
    ConnectionRequestCreate,
    ConnectionRequestResponse,
    ConversationResponse,
)

router = APIRouter(prefix="/connection-requests", tags=["connections"])


@router.post("", response_model=ConnectionRequestResponse, status_code=201)
def create_request(
    payload: ConnectionRequestCreate,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConnectionRequestResponse:
    return execute_idempotent(
        db,
        user_id=user.id,
        scope="connection.request.create",
        key=idempotency_key,
        request_payload=payload.model_dump(),
        operation=lambda: create_connection_request(db, user, payload),
    )


@router.get("", response_model=list[ConnectionRequestResponse])
def get_requests(
    user: CurrentUser,
    db: DbSession,
    direction: str = Query(default="incoming", pattern="^(incoming|outgoing)$"),
    status: str | None = "pending",
) -> list[ConnectionRequestResponse]:
    return list_connection_requests(db, user, direction=direction, status=status)


@router.get("/{request_id}", response_model=ConnectionRequestResponse)
def get_request(
    request_id: str,
    user: CurrentUser,
    db: DbSession,
) -> ConnectionRequestResponse:
    return get_connection_request(db, user, request_id)


@router.post("/{request_id}/accept", response_model=ConversationResponse)
def accept_request(
    request_id: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConversationResponse:
    return execute_idempotent(
        db,
        user_id=user.id,
        scope="connection.request.accept",
        key=idempotency_key,
        request_payload={"request_id": request_id},
        operation=lambda: accept_connection_request(db, user, request_id),
    )


@router.post("/{request_id}/decline", response_model=ConnectionRequestResponse)
def decline_request(
    request_id: str,
    payload: ConnectionDecisionRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> ConnectionRequestResponse:
    return decline_connection_request(db, user, request_id, payload)


@router.delete("/{request_id}", status_code=204)
def cancel_request(
    request_id: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> None:
    cancel_connection_request(db, user, request_id)
