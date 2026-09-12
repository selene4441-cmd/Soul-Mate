from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import DomainError
from app.models import Consent, User, UserSession
from app.security import token_hash

DbSession = Annotated[Session, Depends(get_db)]


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def current_session(request: Request, db: Session) -> UserSession:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise DomainError("AUTH_REQUIRED", "请先登录", status_code=401)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
    if (
        not session
        or session.revoked_at
        or _as_utc(session.expires_at) <= datetime.now(timezone.utc)
    ):
        raise DomainError("SESSION_EXPIRED", "登录已过期，请重新登录", status_code=401)
    return session


def get_current_session(request: Request, db: DbSession) -> UserSession:
    return current_session(request, db)


CurrentSession = Annotated[UserSession, Depends(get_current_session)]


def get_current_user(db: DbSession, session: CurrentSession) -> User:
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        raise DomainError("ACCOUNT_UNAVAILABLE", "账号当前不可用", status_code=403)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def verify_csrf(
    request: Request,
    session: CurrentSession,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not x_csrf_token or x_csrf_token != session.csrf_token:
        raise DomainError("CSRF_INVALID", "请求校验失败，请刷新页面后重试", status_code=403)


CsrfProtected = Annotated[None, Depends(verify_csrf)]


def has_active_consent(db: Session, user_id: str, scope: str) -> bool:
    setting = db.scalar(
        select(Consent)
        .where(
            Consent.user_id == user_id,
            Consent.scope == scope,
            Consent.revoked_at.is_(None),
        )
        .order_by(Consent.granted_at.desc())
    )
    return setting is not None


def require_consent(scope: str) -> Callable[..., User]:
    def dependency(user: CurrentUser, db: DbSession) -> User:
        if not has_active_consent(db, user.id, scope):
            raise DomainError(
                "CONSENT_REQUIRED",
                "需要先授权相应数据处理范围",
                status_code=403,
                details={"scope": scope},
            )
        return user

    return dependency


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise DomainError("FORBIDDEN", "没有管理权限", status_code=403)
    return user
