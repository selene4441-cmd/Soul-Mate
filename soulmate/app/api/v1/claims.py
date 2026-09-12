from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.api.v1.security import CurrentUser, SessionDep, as_utc, require_consent
from app.models import Claim

router = APIRouter(prefix="/claims", tags=["v1/claims"])


def _dt_z(dt) -> str:
    return as_utc(dt).isoformat().replace("+00:00", "Z")


class ClaimOut(BaseModel):
    id: str
    dimension: str
    value: str
    claim_type: str
    evidence_ids: list[str]
    observed_at: str
    expires_at: str
    sensitivity: str
    user_editable: bool
    user_confirmed: bool
    correction_state: dict[str, Any] | None


@router.get("", response_model=list[ClaimOut], dependencies=[Depends(require_consent("matching:v1"))])
def get_claims(user: CurrentUser, db: SessionDep) -> list[ClaimOut]:
    rows = (
        db.execute(select(Claim).where(Claim.user_id == user.id).order_by(Claim.observed_at.desc()))
        .scalars()
        .all()
    )
    return [
        ClaimOut(
            id=row.id,
            dimension=row.dimension,
            value=row.value,
            claim_type=row.claim_type,
            evidence_ids=list(row.evidence_ids or []),
            observed_at=_dt_z(row.observed_at),
            expires_at=_dt_z(row.expires_at),
            sensitivity=row.sensitivity,
            user_editable=bool(row.user_editable),
            user_confirmed=bool(row.user_confirmed),
            correction_state=row.correction_state,
        )
        for row in rows
    ]
