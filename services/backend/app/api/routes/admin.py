from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.dependencies import DbSession, require_admin
from app.models import ModelVersion, PolicyVersion, User
from app.modules.safety import list_safety_events, review_safety_event
from app.schemas import AdminSafetyUpdate, SafetyEventResponse

router = APIRouter(prefix="/admin", tags=["admin"])
AdminUser = Annotated[User, Depends(require_admin)]


@router.get("/safety-events", response_model=list[SafetyEventResponse])
def safety_events(
    _admin: AdminUser,
    db: DbSession,
    status: str | None = None,
) -> list[SafetyEventResponse]:
    return list_safety_events(db, status)


@router.patch("/safety-events/{event_id}", response_model=SafetyEventResponse)
def update_safety_event(
    event_id: str,
    payload: AdminSafetyUpdate,
    admin: AdminUser,
    db: DbSession,
) -> SafetyEventResponse:
    return review_safety_event(db, admin, event_id, payload)


@router.get("/versions")
def versions(
    _admin: AdminUser,
    db: DbSession,
) -> dict[str, list[dict[str, object]]]:
    settings = get_settings()
    models = db.query(ModelVersion).all()
    policies = db.query(PolicyVersion).all()
    return {
        "models": [
            {"id": row.id, "description": row.description, "active": row.active} for row in models
        ]
        or [{"id": settings.model_version, "description": "规则与基础关系信号", "active": True}],
        "policies": [
            {"id": row.id, "description": row.description, "active": row.active} for row in policies
        ]
        or [{"id": settings.policy_version, "description": "冷启动曝光策略", "active": True}],
    }
