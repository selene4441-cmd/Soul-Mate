from __future__ import annotations

from app.models import User


def seed_user(session, *, consent: bool = True, scopes: list[str] | None = None) -> User:
    user = User(consent=consent, consent_scopes=list(scopes or []))
    session.add(user)
    session.commit()
    return user


def test_post_message_requires_conversation_scope(client, api_session) -> None:
    a = seed_user(api_session, consent=True, scopes=[])
    b = seed_user(api_session, consent=True, scopes=["conversation"])

    resp = client.post(
        f"/conversations/{a.id}/{b.id}/messages",
        json={"sender_id": a.id, "content": "hi"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "no_conversation_consent"

