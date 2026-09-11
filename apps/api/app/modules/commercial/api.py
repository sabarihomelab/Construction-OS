from fastapi import APIRouter

from app.modules.commercial.party_router import router as party_router
from app.modules.commercial.router import router as commercial_router

router = APIRouter()
router.include_router(commercial_router)
router.include_router(party_router)
