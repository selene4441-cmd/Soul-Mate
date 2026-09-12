from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.dependencies import CsrfProtected, CurrentSession, CurrentUser, DbSession
from app.errors import DomainError
from app.models import User, UserSession
from app.modules.audit import record_audit
from app.schemas import LoginRequest, RegisterRequest, SessionResponse, SessionUser
from app.security import hash_password, new_token, token_hash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, token: str, csrf_token: str) -> None:
    settings = get_settings()
    max_age = settings.session_ttl_days * 24 * 60 * 60
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _create_session(db: DbSession, user: User) -> tuple[str, UserSession]:
    token = new_token()
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash(token),
        csrf_token=new_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().session_ttl_days),
    )
    db.add(session)
    db.flush()
    return token, session


@router.post("/register", response_model=SessionResponse, status_code=201)
def register(payload: RegisterRequest, response: Response, db: DbSession) -> SessionResponse:
    current_year = datetime.now(timezone.utc).year
    if payload.birth_year > current_year - 18:
        raise DomainError("AGE_REQUIRED", "该产品仅面向成年人", status_code=422)
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise DomainError("EMAIL_EXISTS", "该邮箱已注册", status_code=409)
    user = User(
        display_name=payload.display_name.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        birth_year=payload.birth_year,
        region=payload.region.strip(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError("EMAIL_EXISTS", "该邮箱已注册", status_code=409) from exc
    token, session = _create_session(db, user)
    record_audit(
        db,
        actor_id=user.id,
        action="identity.registered",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    _set_auth_cookies(response, token, session.csrf_token)
    return SessionResponse(user=SessionUser.model_validate(user), csrf_token=session.csrf_token)


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> SessionResponse:
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if (
        not user
        or user.status != "active"
        or not verify_password(payload.password, user.password_hash)
    ):
        raise DomainError("INVALID_CREDENTIALS", "邮箱或密码不正确", status_code=401)
    token, session = _create_session(db, user)
    record_audit(
        db,
        actor_id=user.id,
        action="identity.login",
        entity_type="session",
        entity_id=session.id,
    )
    db.commit()
    _set_auth_cookies(response, token, session.csrf_token)
    return SessionResponse(user=SessionUser.model_validate(user), csrf_token=session.csrf_token)


@router.get("/me", response_model=SessionUser)
def me(user: CurrentUser) -> SessionUser:
    return SessionUser.model_validate(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DbSession,
    user: CurrentUser,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Response:
    session.revoked_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor_id=user.id,
        action="identity.logout",
        entity_type="session",
        entity_id=session.id,
    )
    db.commit()
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    response.status_code = 204
    return response
