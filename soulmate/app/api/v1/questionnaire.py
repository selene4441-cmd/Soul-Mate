from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.errors import APIError
from app.api.v1.questionnaire_def import QUESTIONNAIRE, QUESTIONNAIRE_VERSION
from app.api.v1.security import CurrentUser, SessionDep, as_utc, new_id, now_utc, require_consent
from app.models import Claim, Elicitation, ElicitationKind, Evidence, Response

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


def _elicitation_options_for_question(question: dict[str, Any]) -> list[dict[str, str]]:
    options = question.get("options") or []
    return [
        {"text": str(opt["label"]), "polarity": str(opt.get("polarity") or "uncertain")}
        for opt in options
    ]


def _get_or_create_elicitation(*, db: Session, question: dict[str, Any]) -> Elicitation:
    prompt = str(question["prompt"])
    options_payload = _elicitation_options_for_question(question)

    rows = (
        db.execute(
            select(Elicitation).where(
                Elicitation.question == prompt,
                Elicitation.kind == ElicitationKind.SINGLE_CHOICE,
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        if row.options == options_payload:
            return row

    elicitation = Elicitation(
        question=prompt,
        options=options_payload,
        kind=ElicitationKind.SINGLE_CHOICE,
    )
    db.add(elicitation)
    db.flush()
    return elicitation


def _upsert_response(*, db: Session, user_id: int, elicitation_id: int, choice_text: str) -> None:
    existing = (
        db.execute(
            select(Response).where(
                Response.user_id == user_id,
                Response.elicitation_id == elicitation_id,
            )
        )
        .scalars()
        .all()
    )
    for row in existing:
        db.delete(row)

    db.add(
        Response(
            user_id=user_id,
            elicitation_id=elicitation_id,
            choice=choice_text,
            reaction_time_ms=0,
        )
    )


def _upsert_claim(
    *,
    db: Session,
    user_id: int,
    dimension: str,
    value: str,
    evidence_id: str,
    observed_at,
    expires_at,
) -> str:
    existing = (
        db.execute(select(Claim).where(Claim.user_id == user_id, Claim.dimension == dimension))
        .scalars()
        .all()
    )
    for row in existing:
        db.delete(row)

    claim_id = new_id()
    db.add(
        Claim(
            id=claim_id,
            user_id=user_id,
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
    )
    return claim_id


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

    # Bridge to entropy engine: persist Elicitation + Response so belief_store can replay evidence.
    for dimension, value in payload.answers.items():
        q = by_dim[dimension]
        options = q.get("options") or []
        selected = next((opt for opt in options if opt.get("value") == value), None)
        if selected is None:
            raise APIError(
                code="INVALID_ANSWER",
                message="答案不合法",
                status_code=400,
                details={"dimension": dimension},
            )

        elicitation = _get_or_create_elicitation(db=db, question=q)
        _upsert_response(
            db=db,
            user_id=int(user.id),
            elicitation_id=int(elicitation.id),
            choice_text=str(selected["label"]),
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
        claim_id = _upsert_claim(
            db=db,
            user_id=int(user.id),
            dimension=dimension,
            value=value,
            evidence_id=evidence_id,
            observed_at=observed_at,
            expires_at=expires_at,
        )
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
