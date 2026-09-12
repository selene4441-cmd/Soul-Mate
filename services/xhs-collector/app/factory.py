from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from .config import Settings, get_settings
from .database import ensure_schema, make_engine, make_session_factory
from .routes import router
from .service import refresh_all
from .tikhub import TikhubClient

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger("xhs-collector")


def _refresh_loop(app: FastAPI, stop: threading.Event) -> None:
    interval = app.state.settings.refresh_interval_seconds
    while True:
        if stop.wait(interval):
            return
        try:
            with app.state.session_factory() as db:
                summary = refresh_all(
                    db,
                    app.state.tikhub,
                    interval=app.state.settings.request_interval_seconds,
                )
            logger.info("增量刷新完成: %s", summary)
        except Exception:
            logger.exception("增量刷新任务失败")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()
    app.state.refresh_stop = stop
    if app.state.settings.refresh_enabled:
        thread = threading.Thread(
            target=_refresh_loop,
            args=(app, stop),
            daemon=True,
            name="xhs-refresh",
        )
        thread.start()
    yield
    stop.set()


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    client: TikhubClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if engine is None:
        engine = make_engine(settings.database_url)
    if settings.auto_create_db:
        ensure_schema(engine)

    app = FastAPI(title="小红书客户数据采集", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)
    app.state.tikhub = client if client is not None else TikhubClient(settings)

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app