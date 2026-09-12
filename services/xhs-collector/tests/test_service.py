import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import XhsNote, XhsUser
from app.service import collect_identifiers, refresh_all, sync_notes
from app.tikhub import TikhubError
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

def test_refresh_all_updates_counts_and_timestamp(db):
    lead = XhsUser(
        source="61b46d790000000010008153",
        identifier_type="user_id",
        user_id="61b46d790000000010008153",
        nickname="旧昵称",
        status="fetched",
        followers_count=1200,
    )
    db.add(lead)
    db.commit()

    class Client:
        def fetch_user(self, parsed):
            return {
                "user_id": parsed.user_id,
                "nickname": "新昵称",
                "followers_count": 2000,
                "following_count": 400,
                "notes_count": 100,
                "interaction_count": 99999,
                "raw_json": "{}",
            }

        def close(self):
            pass

    summary = refresh_all(db, Client(), interval=0)
    db.refresh(lead)

    assert summary == {"total": 1, "refreshed": 1, "failed": 0}
    assert lead.followers_count == 2000
    assert lead.notes_count == 100
    assert lead.nickname == "新昵称"
    assert lead.last_refreshed_at is not None
    assert lead.refresh_error is None


def test_refresh_all_skips_needs_review(db):
    db.add(XhsUser(source="757954382", identifier_type="red_id", status="needs_review"))
    db.add(
        XhsUser(
            source="61b46d790000000010008153",
            identifier_type="user_id",
            user_id="61b46d790000000010008153",
            status="fetched",
        )
    )
    db.commit()

    class Client:
        def __init__(self):
            self.calls = 0

        def fetch_user(self, parsed):
            self.calls += 1
            return {"user_id": parsed.user_id, "nickname": "x", "followers_count": 1, "raw_json": "{}"}

        def close(self):
            pass

    client = Client()
    summary = refresh_all(db, client, interval=0)

    assert summary == {"total": 1, "refreshed": 1, "failed": 0}
    assert client.calls == 1


def test_refresh_all_records_error_and_keeps_old_data(db):
    lead = XhsUser(
        source="61b46d790000000010008153",
        identifier_type="user_id",
        user_id="61b46d790000000010008153",
        status="fetched",
        followers_count=1200,
    )
    db.add(lead)
    db.commit()

    class Client:
        def fetch_user(self, parsed):
            raise TikhubError("账号不存在")

        def close(self):
            pass

    summary = refresh_all(db, Client(), interval=0)
    db.refresh(lead)

    assert summary == {"total": 1, "refreshed": 0, "failed": 1}
    assert lead.refresh_error == "账号不存在"
    assert lead.followers_count == 1200

def test_sync_notes_creates_notes_and_fetches_full_content(db):
    lead = XhsUser(
        source="61b46d790000000010008153",
        identifier_type="user_id",
        user_id="61b46d790000000010008153",
        status="fetched",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    client = FakeTikhubClient()
    summary = sync_notes(db, lead, client, interval=0)

    assert summary["found"] == 1
    assert summary["created"] == 1
    assert summary["details"] == 1

    note = db.query(XhsNote).one()
    assert note.note_id == "note-1"
    assert note.desc == "完整正文内容"
    assert json.loads(note.tags) == ["tag1", "tag2"]
    assert json.loads(note.images) == ["https://example.com/note.jpg"]