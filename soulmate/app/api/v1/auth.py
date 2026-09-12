from __future__ import annotations

from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.errors import APIError
from app.api.v1.security import (
    CurrentUser,
    SessionDep,
    clear_auth_cookies,
    create_session,
    hash_password,
    new_csrf_token,
    now_utc,
    set_auth_cookies,
    verify_password,
)
from app.core.config import settings
from app.models import SessionToken, User

router = APIRouter(prefix="/auth", tags=["v1/auth"])


class UserOut(BaseModel):
    id: str
    display_name: str
    email: str
    birth_year: int | None
    region: str
    role: str
    status: str


class AuthOut(BaseModel):
    user: UserOut
    csrf_token: str


class RegisterIn(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    region: str = Field(..., min_length=1, max_length=32)


class LoginIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


def _normalize_email(email: str) -> str:
    v = email.strip().lower()
    if " " in v or "@" not in v or "." not in v.split("@")[-1]:
        raise APIError(code="INVALID_EMAIL", message="邮箱格式不正确", status_code=422)
    return v


def _to_user_out(user: User) -> UserOut:
    if not user.email:
        raise APIError(code="INTERNAL_ERROR", message="用户数据缺失", status_code=500)
    return UserOut(
        id=str(user.id),
        display_name=user.display_name,
        email=user.email,
        birth_year=user.birth_year,
        region=user.region,
        role=user.role,
        status=user.status,
    )


@router.post("/register", response_model=AuthOut)
def register(payload: RegisterIn, response: Response, db: SessionDep) -> AuthOut:
    email = _normalize_email(payload.email)
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise APIError(code="EMAIL_TAKEN", message="邮箱已注册", status_code=409)

    salt = new_csrf_token()
    user = User(
        email=email,
        display_name=payload.display_name,
        birth_year=payload.birth_year,
        region=payload.region,
        role="user",
        status="active",
        password_salt=salt,
        password_hash=hash_password(password=payload.password, salt=salt),
        consent=False,
        consent_scopes=[],
    )
    db.add(user)
    db.flush()

    token = create_session(db=db, user_id=int(user.id))
    csrf_token = new_csrf_token()
    set_auth_cookies(response=response, session_id=token.id, csrf_token=csrf_token)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(code="EMAIL_TAKEN", message="邮箱已注册", status_code=409)

    return AuthOut(user=_to_user_out(user), csrf_token=csrf_token)


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, response: Response, db: SessionDep) -> AuthOut:
    email = _normalize_email(payload.email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not user.password_salt or not user.password_hash:
        raise APIError(code="INVALID_CREDENTIALS", message="邮箱或密码错误", status_code=401)
    if not verify_password(
        password=payload.password, salt=user.password_salt, expected_hash=user.password_hash
    ):
        raise APIError(code="INVALID_CREDENTIALS", message="邮箱或密码错误", status_code=401)

    token = create_session(db=db, user_id=int(user.id))
    csrf_token = new_csrf_token()
    set_auth_cookies(response=response, session_id=token.id, csrf_token=csrf_token)
    db.commit()
    return AuthOut(user=_to_user_out(user), csrf_token=csrf_token)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return _to_user_out(user)


@router.post("/logout")
def logout(
    response: Response,
    db: SessionDep,
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> dict[str, str]:
    if session_id:
        token = db.get(SessionToken, session_id)
        if token is not None and token.revoked_at is None:
            token.revoked_at = now_utc()
            db.add(token)
            db.commit()
    clear_auth_cookies(response=response)
    return {"status": "ok"}
