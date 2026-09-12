from fastapi import APIRouter

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.safety import report_safety_event
from app.schemas import SafetyEventResponse, SafetyReportCreate

router = APIRouter(prefix="/safety", tags=["safety"])


@router.post("/reports", response_model=SafetyEventResponse, status_code=201)
def create_report(
    payload: SafetyReportCreate,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> SafetyEventResponse:
    return report_safety_event(db, user, payload)
