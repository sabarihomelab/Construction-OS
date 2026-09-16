from fastapi import APIRouter

from app.modules.subcontracts.cumulative_router import router as cumulative_router
from app.modules.subcontracts.router import router as core_router

router = APIRouter()
router.include_router(core_router)
router.include_router(cumulative_router)
