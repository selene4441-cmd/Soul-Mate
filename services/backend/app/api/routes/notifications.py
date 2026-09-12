from fastapi import APIRouter

from app.dependencies import CsrfProtected, CurrentUser, DbSession
from app.modules.notifications import list_notifications, mark_notification_read
from app.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def get_notifications(user: CurrentUser, db: DbSession) -> list[NotificationResponse]:
    return list_notifications(db, user)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: str,
    user: CurrentUser,
    db: DbSession,
    _csrf: CsrfProtected,
) -> NotificationResponse:
    return mark_notification_read(db, user, notification_id)
