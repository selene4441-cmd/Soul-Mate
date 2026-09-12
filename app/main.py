from fastapi import FastAPI

from app.api.events import router as events_router

app = FastAPI(title="Soulmate")
app.include_router(events_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
