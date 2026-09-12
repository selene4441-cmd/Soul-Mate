from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from .config import Settings, get_settings
from .database import Base, make_engine, make_session_factory
from .routes import router
from .tikhub import TikhubClient

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    client: TikhubClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if engine is None:
        engine = make_engine(settings.database_url)
    if settings.auto_create_db:
        Base.metadata.create_all(engine)

    app = FastAPI(title="小红书客户数据采集", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)
    app.state.tikhub = client if client is not None else TikhubClient(settings)

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app