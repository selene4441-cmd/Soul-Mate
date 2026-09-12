from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class MatchHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, match_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[match_id].add(websocket)

    async def disconnect(self, match_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(match_id)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._connections.pop(match_id, None)

    async def broadcast(self, match_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections.get(match_id, set()))
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(match_id, ws)

