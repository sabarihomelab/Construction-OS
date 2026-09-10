from fastapi import APIRouter

from app.modules.equipment.consumption_router import router as consumption_router
from app.modules.equipment.router import router as core_router

router = APIRouter()
router.include_router(core_router)
router.include_router(consumption_router)
