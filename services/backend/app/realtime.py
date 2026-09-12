from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class RealtimeHub:
    """单实例连接中心；跨实例事件由 Outbox/Redis 消费器转发。"""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[conversation_id].add(websocket)

    async def disconnect(self, conversation_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[conversation_id].discard(websocket)
            if not self._connections[conversation_id]:
                self._connections.pop(conversation_id, None)

    async def broadcast(self, conversation_id: str, payload: dict) -> None:
        async with self._lock:
            recipients = list(self._connections.get(conversation_id, set()))
        stale: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(conversation_id, websocket)


realtime_hub = RealtimeHub()
