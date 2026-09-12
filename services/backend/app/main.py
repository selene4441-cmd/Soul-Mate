from __future__ import annotations

import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.errors import DomainError
from app.realtime import redis_event_bridge
from app.seed import seed_demo_data

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create_db:
        Base.metadata.create_all(bind=engine)
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    await redis_event_bridge.start()
    try:
        yield
    finally:
        await redis_event_bridge.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="同频 v0.1 API。浏览器端不会接收内部排序分数或原始模型特征。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rate_windows: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMITS = {
    "/auth/login": (20, 60),
    "/auth/register": (10, 3600),
    "/questionnaire/submissions": (10, 3600),
    "/recommendations": (30, 3600),
    "/invitations": (30, 3600),
    "/safety/reports": (10, 3600),
}


@app.middleware("http")
async def request_safety_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or uuid4().hex
    request.state.trace_id = trace_id
    if settings.rate_limit_enabled:
        for suffix, (limit, window) in RATE_LIMITS.items():
            if request.url.path.endswith(suffix):
                client = request.client.host if request.client else "unknown"
                bucket_key = f"{client}:{suffix}"
                now = time.monotonic()
                bucket = _rate_windows[bucket_key]
                while bucket and now - bucket[0] > window:
                    bucket.popleft()
                if len(bucket) >= limit:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "code": "RATE_LIMITED",
                            "message": "请求过于频繁，请稍后再试",
                            "trace_id": trace_id,
                            "details": None,
                        },
                        headers={"Retry-After": str(window), "X-Trace-ID": trace_id},
                    )
                bucket.append(now)
                break
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self' ws: wss:; frame-ancestors 'none'"
    )
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid4().hex)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "trace_id": trace_id,
            "details": exc.details,
        },
        headers={"X-Trace-ID": trace_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid4().hex)
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求内容不完整或格式不正确",
            "trace_id": trace_id,
            "details": exc.errors(),
        },
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid4().hex)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "trace_id": trace_id,
            "details": None,
        },
    )


app.include_router(api_router, prefix=settings.api_prefix)
