from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.errors import APIError
from app.core.config import settings
from app.core.db import get_session
from app.models import Consent, SessionToken, User


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def new_id() -> str:
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_password(*, password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
    )
    return dk.hex()


def verify_password(*, password: str, salt: str, expected_hash: str) -> bool:
    got = hash_password(password=password, salt=salt)
    return hmac.compare_digest(got, expected_hash)


def set_auth_cookies(*, response, session_id: str, csrf_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=int(settings.session_ttl_seconds),
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=int(settings.session_ttl_seconds),
    )


def clear_auth_cookies(*, response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.delete_cookie(key=settings.csrf_cookie_name, path="/")


SessionDep = Annotated[Session, Depends(get_session)]


def _require_session(*, db: Session, session_id: str | None) -> SessionToken:
    if not session_id:
        raise APIError(code="UNAUTHORIZED", message="未登录", status_code=401)

    token = db.get(SessionToken, session_id)
    if token is None or token.revoked_at is not None or as_utc(token.expires_at) <= now_utc():
        raise APIError(code="UNAUTHORIZED", message="未登录", status_code=401)
    return token


def get_current_user(
    request: Request,
    db: SessionDep,
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    token = _require_session(db=db, session_id=session_id)
    user = db.get(User, token.user_id)
    if user is None:
        raise APIError(code="UNAUTHORIZED", message="未登录", status_code=401)
    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_consent(scope: str):
    def _dep(user: CurrentUser, db: SessionDep) -> None:
        row = (
            db.execute(
                select(Consent).where(
                    Consent.user_id == user.id,
                    Consent.scope == scope,
                    Consent.revoked_at.is_(None),
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            raise APIError(
                code="CONSENT_REQUIRED",
                message="需要先授权匹配用途" if scope == "matching:v1" else "需要先授权用途",
                status_code=403,
                details={"scope": scope},
            )

    return _dep


def create_session(*, db: Session, user_id: int) -> SessionToken:
    session_id = new_id()
    token = SessionToken(
        id=session_id,
        user_id=user_id,
        expires_at=now_utc() + timedelta(seconds=int(settings.session_ttl_seconds)),
        revoked_at=None,
    )
    db.add(token)
    return token
