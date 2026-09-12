from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.agent import router as agent_router
from app.api.conversations import router as conversations_router
from app.api.events import router as events_router
from app.api.extensions import router as extensions_router
from app.api.relationships import router as relationships_router
from app.api.v1.csrf import V1CSRFMiddleware
from app.api.v1.errors import V1TraceAndErrorMiddleware
from app.api.v1.handlers import http_exception_handler, validation_exception_handler
from app.api.v1.router import router as v1_router
from app.api.v1.ws_hub import MatchHub

app = FastAPI(title="Soulmate")
app.state.match_hub = MatchHub()

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(V1CSRFMiddleware)
app.add_middleware(V1TraceAndErrorMiddleware)

app.include_router(v1_router)
app.include_router(events_router)
app.include_router(extensions_router)
app.include_router(agent_router)
app.include_router(relationships_router)
app.include_router(conversations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
