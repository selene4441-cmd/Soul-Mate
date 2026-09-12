from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.main import app
from app.core.db import get_session


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def api_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def api_session(api_engine) -> Session:
    with Session(api_engine) as db_session:
        yield db_session


@pytest.fixture()
def client(api_engine) -> TestClient:
    def _override_get_session():
        with Session(api_engine) as db_session:
            yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    app.state.rate_limiter = None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def scratch_dir() -> Path:
    base = Path("data") / "artifacts"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"run-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
