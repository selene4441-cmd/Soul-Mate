from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import suppress
from typing import Any

from fastapi import WebSocket
from redis import asyncio as redis_asyncio

from app.config import get_settings


class RealtimeHub:
    """单实例连接中心；跨实例事件通过 Redis Pub/Sub 转发。"""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[channel].add(websocket)

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                self._connections.pop(channel, None)

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            recipients = list(self._connections.get(channel, set()))
        stale: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(channel, websocket)


class RedisEventBridge:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._client = None

    async def start(self) -> None:
        if not get_settings().realtime_broker_enabled or self._task:
            return
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _listen(self) -> None:
        while True:
            try:
                self._client = redis_asyncio.from_url(
                    get_settings().redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
                pubsub = self._client.pubsub()
                await pubsub.subscribe("tongpin:events")
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    await self._dispatch(str(message.get("data", "")))
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1)

    async def _dispatch(self, raw: str) -> None:
        try:
            envelope = json.loads(raw)
            event = envelope["event"]
            for channel in envelope.get("channels", []):
                local_channel = channel
                if channel.startswith("tongpin:conversation:") and channel.endswith(":events"):
                    local_channel = channel.removeprefix("tongpin:conversation:").removesuffix(
                        ":events"
                    )
                elif channel.startswith("tongpin:user:") and channel.endswith(":events"):
                    local_channel = "user:" + channel.removeprefix("tongpin:user:").removesuffix(
                        ":events"
                    )
                await realtime_hub.broadcast(local_channel, event)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return


realtime_hub = RealtimeHub()
redis_event_bridge = RedisEventBridge()
