from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1.errors import APIError
from app.api.v1.security import CurrentUser, SessionDep, as_utc, new_id, now_utc
from app.models import Consent, User

router = APIRouter(prefix="/consents", tags=["v1/consents"])

SUPPORTED_SCOPES = {"matching:v1", "conversation:v1", "outcomes:v1"}


class ConsentIn(BaseModel):
    scope: str = Field(..., min_length=1, max_length=64)
    purpose: str = Field(..., min_length=1, max_length=128)


class ConsentOut(BaseModel):
    scope: str
    purpose: str
    granted_at: str


def _sync_legacy_user_fields(*, user: User) -> None:
    user.consent = True
    scopes = set(user.consent_scopes or [])
    if "conversation:v1" in scopes:
        scopes.add("conversation")
    if "matching:v1" in scopes:
        scopes.add("matching")
    if "outcomes:v1" in scopes:
        scopes.add("outcomes")
    user.consent_scopes = sorted(scopes)


@router.get("", response_model=list[ConsentOut])
def get_consents(user: CurrentUser, db: SessionDep) -> list[ConsentOut]:
    rows = (
        db.execute(select(Consent).where(Consent.user_id == user.id, Consent.revoked_at.is_(None)))
        .scalars()
        .all()
    )
    return [
        ConsentOut(scope=row.scope, purpose=row.purpose, granted_at=as_utc(row.granted_at).isoformat())
        for row in rows
    ]


@router.post("", response_model=ConsentOut)
def post_consent(
    payload: ConsentIn, user: CurrentUser, db: SessionDep
) -> ConsentOut:
    if payload.scope not in SUPPORTED_SCOPES:
        raise APIError(
            code="UNSUPPORTED_SCOPE",
            message="不支持的授权范围",
            status_code=400,
            details={"scope": payload.scope},
        )

    row = (
        db.execute(select(Consent).where(Consent.user_id == user.id, Consent.scope == payload.scope))
        .scalars()
        .one_or_none()
    )
    now = now_utc()
    if row is None:
        row = Consent(
            id=new_id(),
            user_id=int(user.id),
            scope=payload.scope,
            purpose=payload.purpose,
            granted_at=now,
            revoked_at=None,
        )
        db.add(row)
    else:
        row.purpose = payload.purpose
        row.granted_at = now
        row.revoked_at = None
        db.add(row)

    scopes = set(user.consent_scopes or [])
    scopes.add(payload.scope)
    user.consent_scopes = sorted(scopes)
    _sync_legacy_user_fields(user=user)

    db.add(user)
    db.commit()
    return ConsentOut(scope=row.scope, purpose=row.purpose, granted_at=as_utc(row.granted_at).isoformat())
