from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.dependencies import has_active_consent
from app.models import Match, User, UserSession
from app.modules.interaction import list_messages, send_message
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


@router.websocket("/ws/matches/{match_id}")
async def conversation_socket(websocket: WebSocket, match_id: str) -> None:
    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=4403)
        return
    settings = get_settings()
    token = websocket.cookies.get(settings.session_cookie_name)
    if not token:
        await websocket.close(code=4401)
        return

    with SessionLocal() as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
        if (
            not session
            or session.revoked_at
            or _as_utc(session.expires_at) <= datetime.now(timezone.utc)
        ):
            await websocket.close(code=4401)
            return
        user = db.get(User, session.user_id)
        if not user or user.status != "active":
            await websocket.close(code=4401)
            return
        match = db.scalar(
            select(Match).where(
                Match.id == match_id,
                ((Match.user_a_id == user.id) | (Match.user_b_id == user.id)),
            )
        )
        if not match or match.status != "connected":
            await websocket.close(code=4404)
            return
        if not has_active_consent(db, user.id, "conversation:v1"):
            await websocket.close(code=4403)
            return
        initial = [item.model_dump(mode="json") for item in list_messages(db, user, match_id)]
        conversation_id = initial[0]["conversation_id"] if initial else None
        if conversation_id is None:
            from app.models import Conversation

            conversation = db.scalar(select(Conversation).where(Conversation.match_id == match_id))
            conversation_id = conversation.id if conversation else None
        if conversation_id is None:
            await websocket.close(code=4404)
            return
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
                if not user or not has_active_consent(db, user.id, "conversation:v1"):
                    await websocket.close(code=4403)
                    return
                try:
                    message = send_message(
                        db,
                        user,
                        match_id,
                        MessageCreate(
                            body=str(payload.get("body", "")),
                            client_message_id=str(payload.get("client_message_id", "")),
                        ),
                    )
                except Exception:
                    await websocket.send_json({"type": "error", "code": "MESSAGE_REJECTED"})
                    continue
                envelope = {"type": "message.created", "data": message.model_dump(mode="json")}
            await realtime_hub.broadcast(conversation_id, envelope)
    except WebSocketDisconnect:
        await realtime_hub.disconnect(conversation_id, websocket)
