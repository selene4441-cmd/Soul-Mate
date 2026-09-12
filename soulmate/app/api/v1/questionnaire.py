from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.errors import APIError
from app.api.v1.questionnaire_def import QUESTIONNAIRE, QUESTIONNAIRE_VERSION
from app.api.v1.security import CurrentUser, SessionDep, as_utc, new_id, now_utc, require_consent
from app.models import Claim, Evidence

router = APIRouter(prefix="/questionnaire", tags=["v1/questionnaire"])


def _dt_z(dt) -> str:
    return as_utc(dt).isoformat().replace("+00:00", "Z")


class QuestionnaireSubmissionIn(BaseModel):
    version: str = Field(..., min_length=1, max_length=64)
    answers: dict[str, str] = Field(default_factory=dict)


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


@router.get("")
def get_questionnaire() -> dict[str, Any]:
    return dict(QUESTIONNAIRE)


@router.post(
    "/submissions",
    response_model=list[ClaimOut],
    dependencies=[Depends(require_consent("matching:v1"))],
)
def submit_questionnaire(
    payload: QuestionnaireSubmissionIn,
    user: CurrentUser,
    db: SessionDep,
) -> list[ClaimOut]:
    if payload.version != QUESTIONNAIRE_VERSION:
        raise APIError(
            code="QUESTIONNAIRE_VERSION_MISMATCH",
            message="问卷版本不匹配",
            status_code=400,
            details={"expected": QUESTIONNAIRE_VERSION, "got": payload.version},
        )

    questions = QUESTIONNAIRE["questions"]
    by_dim = {q["dimension"]: q for q in questions}
    missing_required = [
        q["dimension"]
        for q in questions
        if q.get("required") and q["dimension"] not in payload.answers
    ]
    if missing_required:
        raise APIError(
            code="QUESTIONNAIRE_INCOMPLETE",
            message="问卷未完成",
            status_code=400,
            details={"missing": missing_required},
        )

    for dimension, value in payload.answers.items():
        q = by_dim.get(dimension)
        if not q:
            raise APIError(
                code="UNKNOWN_QUESTION",
                message="未知题目",
                status_code=400,
                details={"dimension": dimension},
            )
        allowed = {opt["value"] for opt in q.get("options") or []}
        if allowed and value not in allowed:
            raise APIError(
                code="INVALID_ANSWER",
                message="答案不合法",
                status_code=400,
                details={"dimension": dimension},
            )

    evidence_id = new_id()
    evidence = Evidence(
        id=evidence_id,
        user_id=int(user.id),
        kind="questionnaire",
        payload={"version": payload.version, "answers": payload.answers},
    )
    db.add(evidence)

    observed_at = now_utc()
    expires_at = observed_at + timedelta(days=30)

    out: list[ClaimOut] = []
    for dimension, value in payload.answers.items():
        claim_id = new_id()
        claim = Claim(
            id=claim_id,
            user_id=int(user.id),
            dimension=dimension,
            value=value,
            claim_type="preference",
            evidence_ids=[evidence_id],
            observed_at=observed_at,
            expires_at=expires_at,
            sensitivity="L1",
            user_editable=True,
            user_confirmed=True,
            correction_state=None,
        )
        db.add(claim)
        out.append(
            ClaimOut(
                id=claim_id,
                dimension=dimension,
                value=value,
                claim_type="preference",
                evidence_ids=[evidence_id],
                observed_at=_dt_z(observed_at),
                expires_at=_dt_z(expires_at),
                sensitivity="L1",
                user_editable=True,
                user_confirmed=True,
                correction_state=None,
            )
        )

    db.commit()
    return out
