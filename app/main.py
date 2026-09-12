from fastapi import FastAPI

from app.api.agent import router as agent_router
from app.api.conversations import router as conversations_router
from app.api.events import router as events_router
from app.api.extensions import router as extensions_router
from app.api.relationships import router as relationships_router

app = FastAPI(title="Soulmate")
app.include_router(events_router)
app.include_router(extensions_router)
app.include_router(agent_router)
app.include_router(relationships_router)
app.include_router(conversations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
