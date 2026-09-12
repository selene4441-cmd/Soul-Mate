from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.security import SessionDep, as_utc
from app.api.v1.ws_hub import MatchHub
from app.core.config import settings
from app.models import Match, MatchMessage, SessionToken, User

router = APIRouter(prefix="/ws", tags=["v1/ws"])


def _require_ws_user(*, websocket: WebSocket, db: Session) -> User | None:
    session_id = websocket.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    token = db.get(SessionToken, session_id)
    if token is None or token.revoked_at is not None or as_utc(token.expires_at) <= datetime.now(tz=UTC):
        return None
    user = db.get(User, token.user_id)
    return user


@router.websocket("/matches/{match_id}")
async def ws_match(websocket: WebSocket, match_id: str, db: SessionDep) -> None:
    # 注意：必须「先 accept 再 close」，否则 uvicorn 会把握手阶段的 close 降级成
    # HTTP 403，浏览器只能看到 1006，无法区分「未登录」与「不属于该会话」。
    user = _require_ws_user(websocket=websocket, db=db)
    if user is None:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    match = db.get(Match, match_id)
    if match is None or user.id not in {match.user_a_id, match.user_b_id}:
        await websocket.accept()
        await websocket.close(code=4403)
        return

    hub: MatchHub = getattr(websocket.app.state, "match_hub", None) or MatchHub()
    websocket.app.state.match_hub = hub

    await hub.connect(match_id, websocket)
    try:
        rows = (
            db.execute(
                select(MatchMessage)
                .where(MatchMessage.match_id == match_id)
                .order_by(MatchMessage.created_at.asc())
            )
            .scalars()
            .all()
        )
        await websocket.send_json({"type": "messages.snapshot", "data": []})
        for row in rows:
            await websocket.send_json(
                {"type": "message.created", "data": {"id": row.id, "body": row.body}}
            )

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(match_id, websocket)
