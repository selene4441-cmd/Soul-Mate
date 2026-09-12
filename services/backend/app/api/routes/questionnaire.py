from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.dependencies import CsrfProtected, DbSession, require_consent
from app.models import User
from app.modules.audit import execute_idempotent
from app.modules.claims import submit_questionnaire
from app.questionnaire_data import get_questionnaire
from app.schemas import ClaimResponse, QuestionnaireResponse, QuestionnaireSubmission

router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])


@router.get("", response_model=QuestionnaireResponse)
def questionnaire() -> QuestionnaireResponse:
    return QuestionnaireResponse.model_validate(get_questionnaire())


@router.post("/submissions", response_model=list[ClaimResponse])
def create_submission(
    payload: QuestionnaireSubmission,
    user: Annotated[User, Depends(require_consent("matching:v1"))],
    db: DbSession,
    _csrf: CsrfProtected,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> list[ClaimResponse]:
    return execute_idempotent(
        db,
        user_id=user.id,
        scope="questionnaire.submit",
        key=idempotency_key,
        request_payload=payload.model_dump(),
        operation=lambda: submit_questionnaire(db, user, payload),
    )
