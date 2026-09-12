from fastapi import APIRouter

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.claims import delete_claim, feedback_claim, list_claims, update_claim
from app.schemas import ClaimFeedbackRequest, ClaimResponse, ClaimUpdateRequest

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=list[ClaimResponse])
def get_claims(
    user: CurrentUser,
    db: DbSession,
    include_expired: bool = False,
) -> list[ClaimResponse]:
    return list_claims(db, user, include_expired=include_expired)


@router.post("/{claim_id}/feedback", response_model=ClaimResponse)
def claim_feedback(
    claim_id: str,
    payload: ClaimFeedbackRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> ClaimResponse:
    return feedback_claim(db, user, claim_id, payload)


@router.patch("/{claim_id}", response_model=ClaimResponse)
def edit_claim(
    claim_id: str,
    payload: ClaimUpdateRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> ClaimResponse:
    return update_claim(db, user, claim_id, payload)


@router.delete("/{claim_id}", status_code=204)
def remove_claim(
    claim_id: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> None:
    delete_claim(db, user, claim_id)
