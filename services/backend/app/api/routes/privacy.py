from fastapi import APIRouter, Response

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.privacy import delete_user_data

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.delete("/me", status_code=202)
def delete_me(
    response: Response,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> dict[str, str]:
    request = delete_user_data(db, user)
    response.delete_cookie("tongpin_session", path="/")
    response.delete_cookie("tongpin_csrf", path="/")
    return {"request_id": request.id, "status": request.status}
