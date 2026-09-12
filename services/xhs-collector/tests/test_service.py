import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import XhsUser
from app.service import collect_identifiers
from fakes import FakeTikhubClient


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        yield session


def test_collect_hex_uid_creates_and_updates(db):
    client = FakeTikhubClient()
    results = collect_identifiers(db, "61b46d790000000010008153", client, interval=0)
    assert results[0].status == "created"
    assert results[0].nickname == "测试用户"

    lead = db.query(XhsUser).one()
    assert lead.user_id == "61b46d790000000010008153"
    assert lead.followers_count == 1200
    assert lead.status == "fetched"

    results2 = collect_identifiers(db, "61b46d790000000010008153", client, interval=0)
    assert results2[0].status == "updated"
    assert db.query(XhsUser).count() == 1


def test_collect_share_text_creates(db):
    client = FakeTikhubClient()
    results = collect_identifiers(db, "http://xhslink.com/a/xyz", client, interval=0)
    assert results[0].status == "created"
    assert client.calls[0].share_text == "http://xhslink.com/a/xyz"


def test_collect_red_id_goes_to_needs_review_without_api_call(db):
    client = FakeTikhubClient()
    results = collect_identifiers(db, "757954382", client, interval=0)
    assert results[0].status == "needs_review"

    lead = db.query(XhsUser).one()
    assert lead.red_id == "757954382"
    assert lead.status == "needs_review"
    assert client.calls == []


def test_collect_failed_uid_is_recorded(db):
    client = FakeTikhubClient(fail_values={"000000000000000000000000"})
    results = collect_identifiers(db, "000000000000000000000000", client, interval=0)
    assert results[0].status == "failed"
    assert db.query(XhsUser).one().status == "failed"