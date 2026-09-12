from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
)
from fastapi.exception_handlers import (
    request_validation_exception_handler as default_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.errors import APIError, error_response, new_trace_id


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if not request.url.path.startswith("/api/v1/"):
        return await default_http_exception_handler(request, exc)

    trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
    detail: Any = exc.detail
    if isinstance(detail, dict) and {"code", "message"} <= set(detail.keys()):
        err = APIError(
            code=str(detail["code"]),
            message=str(detail["message"]),
            status_code=int(exc.status_code),
            details=dict(detail.get("details") or {}),
        )
        return error_response(err=err, trace_id=trace_id)

    return error_response(
        err=APIError(
            code="HTTP_ERROR",
            message=str(detail) if detail is not None else "请求失败",
            status_code=int(exc.status_code),
        ),
        trace_id=trace_id,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    if not request.url.path.startswith("/api/v1/"):
        return await default_validation_exception_handler(request, exc)

    trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
    return error_response(
        err=APIError(
            code="VALIDATION_ERROR",
            message="请求参数错误",
            status_code=422,
            details={"errors": exc.errors()},
        ),
        trace_id=trace_id,
    )

