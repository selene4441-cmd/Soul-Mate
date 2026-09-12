import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.factory import create_app
from fakes import FakeTikhubClient


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    settings = Settings(
        database_url="sqlite://",
        tikhub_api_key="test-key",
        request_interval_seconds=0,
        auto_create_db=True,
    )
    app = create_app(settings=settings, engine=engine, client=FakeTikhubClient())
    with TestClient(app) as test_client:
        yield test_client


def test_collect_red_id_and_list(client):
    response = client.post("/api/v1/collect", json={"text": "757954382"})
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["needs_review"] == 1
    assert data["results"][0]["lead_id"] is not None

    response = client.get("/api/v1/leads")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["red_id"] == "757954382"
    assert items[0]["status"] == "needs_review"


def test_resolve_lead(client):
    response = client.post("/api/v1/collect", json={"text": "757954382"})
    lead_id = response.json()["results"][0]["lead_id"]

    response = client.post(
        f"/api/v1/leads/{lead_id}/resolve",
        json={"user_id": "61b46d790000000010008153"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fetched"
    assert body["nickname"] == "测试用户"
    assert body["user_id"] == "61b46d790000000010008153"


def test_export_csv(client):
    client.post("/api/v1/collect", json={"text": "757954382"})
    response = client.get("/api/v1/leads/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "757954382" in response.text

def test_index_page_serves_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "小红书客户数据采集" in response.text