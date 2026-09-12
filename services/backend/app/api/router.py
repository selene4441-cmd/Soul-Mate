from fastapi import APIRouter

from app.api import websocket
from app.api.routes import (
    admin,
    auth,
    blocks,
    claims,
    connections,
    consents,
    conversations,
    health,
    interaction,
    notifications,
    outcomes,
    privacy,
    questionnaire,
    recommendations,
    safety,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(consents.router)
api_router.include_router(questionnaire.router)
api_router.include_router(claims.router)
api_router.include_router(recommendations.router)
api_router.include_router(connections.router)
api_router.include_router(conversations.router)
api_router.include_router(blocks.router)
api_router.include_router(notifications.router)
api_router.include_router(interaction.router)
api_router.include_router(outcomes.router)
api_router.include_router(safety.router)
api_router.include_router(admin.router)
api_router.include_router(privacy.router)
api_router.include_router(websocket.router)
