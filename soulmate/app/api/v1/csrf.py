from __future__ import annotations

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.v1.errors import APIError
from app.core.config import settings

UNSAFE_METHODS = {"POST", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {"/api/v1/auth/register", "/api/v1/auth/login"}


class V1CSRFMiddleware:
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

        method = (scope.get("method") or "").upper()
        if method not in UNSAFE_METHODS or path in CSRF_EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        cookie_token = request.cookies.get(settings.csrf_cookie_name)
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or not header_token or cookie_token != header_token:
            raise APIError(code="CSRF_INVALID", message="CSRF token invalid", status_code=403)

        await self.app(scope, receive, send)
