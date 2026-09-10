from fastapi import APIRouter

from app.modules.financials.feed_router import router as feed_router
from app.modules.financials.router import router as core_router

router = APIRouter()
router.include_router(core_router)
router.include_router(feed_router)
