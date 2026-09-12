from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header

from app.dependencies import CsrfProtected, CurrentUser, DbSession, require_consent
from app.models import User
from app.modules.audit import execute_idempotent
from app.modules.connections import connection_cues
from app.modules.matching import generate_recommendations, get_candidate_lead, record_action
from app.schemas import ActionRequest, CandidateLead, CueOption, RecommendationBundle

router = APIRouter(prefix="/recommendations", tags=["matching"])


@router.post("", response_model=RecommendationBundle)
def create_recommendations(
    user: Annotated[User, Depends(require_consent("matching:v1"))],
    db: DbSession,
    _csrf: CsrfProtected,
    session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RecommendationBundle:
    sid = session_id or uuid4().hex
    return execute_idempotent(
        db,
        user_id=user.id,
        scope="recommendation.generate",
        key=idempotency_key,
        request_payload={"session_id": sid},
        operation=lambda: generate_recommendations(db, user, session_id=sid),
    )


@router.get("/{candidate_id}", response_model=CandidateLead)
def get_recommendation(
    candidate_id: str,
    user: Annotated[User, Depends(require_consent("matching:v1"))],
    db: DbSession,
) -> CandidateLead:
    return get_candidate_lead(db, user, candidate_id)


@router.get("/{candidate_id}/cues", response_model=list[CueOption])
def get_connection_cues(
    candidate_id: str,
    user: Annotated[User, Depends(require_consent("matching:v1"))],
    db: DbSession,
) -> list[CueOption]:
    return connection_cues(db, user, candidate_id)


@router.post("/{candidate_id}/actions", status_code=204)
def create_action(
    candidate_id: str,
    payload: ActionRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> None:
    record_action(db, user, candidate_id, payload)
