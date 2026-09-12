from fastapi import APIRouter

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.consent import grant_consent, list_consents, revoke_consent
from app.schemas import ConsentRequest, ConsentResponse

router = APIRouter(prefix="/consents", tags=["consent"])


@router.get("", response_model=list[ConsentResponse])
def get_consents(user: CurrentUser, db: DbSession) -> list[ConsentResponse]:
    return list_consents(db, user)


@router.post("", response_model=ConsentResponse)
def create_consent(
    payload: ConsentRequest,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> ConsentResponse:
    return grant_consent(db, user, payload)


@router.delete("/{scope}", response_model=ConsentResponse)
def remove_consent(
    scope: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> ConsentResponse:
    return revoke_consent(db, user, scope)
