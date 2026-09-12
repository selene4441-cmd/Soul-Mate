from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.dependencies import has_active_consent
from app.errors import DomainError
from app.models import Conversation, ConversationMember, Match, User, UserSession
from app.modules.conversations import conversation_for_user
from app.modules.messages import list_messages_page, send_message
from app.modules.notifications import list_notifications
from app.realtime import realtime_hub
from app.schemas import MessageCreate
from app.security import token_hash

router = APIRouter(tags=["realtime"])


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return get_settings().environment != "production"
    allowed = {get_settings().app_origin}
    if get_settings().environment != "production":
        allowed.update({"http://localhost:3000", "http://127.0.0.1:3000"})
        hostname = (urlparse(origin).hostname or "").lower()
        if hostname.endswith(".app.github.dev"):
            return True
    return origin in allowed


def _authenticated_user(websocket: WebSocket, db) -> User | None:
    settings = get_settings()
    token = websocket.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
    if (
        not session
        or session.revoked_at
        or _as_utc(session.expires_at) <= datetime.now(timezone.utc)
    ):
        return None
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        return None
    return user


async def _conversation_socket(websocket: WebSocket, conversation_id: str) -> None:
    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=4403)
        return
    with SessionLocal() as db:
        user = _authenticated_user(websocket, db)
        if not user:
            await websocket.close(code=4401)
            return
        try:
            conversation = conversation_for_user(db, user, conversation_id)
        except DomainError:
            await websocket.close(code=4404)
            return
        if conversation.status != "active":
            await websocket.close(code=4409)
            return
        member_ids = set(
            db.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation.id
                )
            ).all()
        )
        if any(not has_active_consent(db, member_id, "conversation:v1") for member_id in member_ids):
            await websocket.close(code=4403)
            return
        initial = [
            item.model_dump(mode="json")
            for item in list_messages_page(db, user, conversation.id, limit=100).items
        ]
        user_id = user.id

    await realtime_hub.connect(conversation_id, websocket)
    await websocket.send_json({"type": "messages.snapshot", "data": initial})
    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if payload.get("type") != "message":
                await websocket.send_json({"type": "error", "code": "UNSUPPORTED_EVENT"})
                continue
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if not user:
                    await websocket.close(code=4401)
                    return
                try:
                    message = send_message(
                        db,
                        user,
                        conversation_id,
                        MessageCreate(
                            body=str(payload.get("body", "")),
                            client_message_id=str(payload.get("client_message_id", "")),
                            kind=str(payload.get("kind", "text")),
                        ),
                    )
                except DomainError as exc:
                    await websocket.send_json({"type": "error", "code": exc.code})
                    continue
                envelope = {"type": "message.created", "data": message.model_dump(mode="json")}
            await realtime_hub.broadcast(conversation_id, envelope)
    except WebSocketDisconnect:
        await realtime_hub.disconnect(conversation_id, websocket)


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_socket(websocket: WebSocket, conversation_id: str) -> None:
    await _conversation_socket(websocket, conversation_id)


@router.websocket("/ws/matches/{match_id}")
async def legacy_match_socket(websocket: WebSocket, match_id: str) -> None:
    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=4403)
        return
    with SessionLocal() as db:
        user = _authenticated_user(websocket, db)
        if not user:
            await websocket.close(code=4401)
            return
        match = db.scalar(
            select(Match).where(
                Match.id == match_id,
                ((Match.user_a_id == user.id) | (Match.user_b_id == user.id)),
            )
        )
        if not match or match.status not in {"active", "connected"}:
            await websocket.close(code=4404)
            return
        conversation = db.scalar(select(Conversation).where(Conversation.match_id == match.id))
        conversation_id = conversation.id if conversation else None
    if not conversation_id:
        await websocket.close(code=4404)
        return
    await _conversation_socket(websocket, conversation_id)


@router.websocket("/ws/me")
async def user_events_socket(websocket: WebSocket) -> None:
    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=4403)
        return
    with SessionLocal() as db:
        user = _authenticated_user(websocket, db)
        if not user:
            await websocket.close(code=4401)
            return
        user_id = user.id
        initial = [item.model_dump(mode="json") for item in list_notifications(db, user)]
    await realtime_hub.connect(f"user:{user_id}", websocket)
    await websocket.send_json({"type": "notifications.snapshot", "data": initial})
    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await realtime_hub.disconnect(f"user:{user_id}", websocket)
