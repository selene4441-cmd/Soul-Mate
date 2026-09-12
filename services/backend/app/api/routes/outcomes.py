from fastapi import APIRouter

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.outcomes import list_outcomes, submit_outcome
from app.schemas import OutcomeCreate, OutcomeResponse

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.get("", response_model=list[OutcomeResponse])
def get_outcomes(user: CurrentUser, db: DbSession) -> list[OutcomeResponse]:
    return list_outcomes(db, user)


@router.post("", response_model=OutcomeResponse)
def create_outcome(
    payload: OutcomeCreate,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> OutcomeResponse:
    return submit_outcome(db, user, payload)
