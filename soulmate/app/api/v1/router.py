from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, claims, consents, invitations, matches, questionnaire, recommendations, space, ws

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(consents.router)
router.include_router(questionnaire.router)
router.include_router(claims.router)
router.include_router(recommendations.router)
router.include_router(invitations.router)
router.include_router(matches.router)
router.include_router(ws.router)
router.include_router(space.router)

