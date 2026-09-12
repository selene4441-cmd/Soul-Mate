from __future__ import annotations

import uuid
from typing import Any

from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def new_trace_id() -> str:
    return uuid.uuid4().hex


class APIError(Exception):
    __slots__ = ("code", "message", "status_code", "details")

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_response(*, err: APIError, trace_id: str) -> JSONResponse:
    payload: dict[str, Any] = {
        "code": err.code,
        "message": err.message,
        "trace_id": trace_id,
        "details": err.details or {},
    }
    return JSONResponse(payload, status_code=err.status_code)


def _find_api_error(exc: BaseException) -> APIError | None:
    if isinstance(exc, APIError):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for e in exc.exceptions:
            found = _find_api_error(e)
            if found is not None:
                return found
    return None


class V1TraceAndErrorMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if not path.startswith("/api/v1/"):
            await self.app(scope, receive, send)
            return

        trace_id = new_trace_id()
        scope.setdefault("state", {})["trace_id"] = trace_id

        async def send_with_trace(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.get("headers") or [])
                headers["X-Trace-Id"] = trace_id
                message["headers"] = headers.raw
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        except Exception as e:
            found = _find_api_error(e)
            if found is None:
                found = APIError(
                    code="INTERNAL_ERROR",
                    message="服务异常",
                    status_code=500,
                )
            resp = error_response(err=found, trace_id=trace_id)
            resp.headers["X-Trace-Id"] = trace_id
            await resp(scope, receive, send)
