from fastapi import APIRouter

from app.modules.procurement.router import router as core_router
from app.modules.procurement.sourcing_router import router as sourcing_router

router = APIRouter()
router.include_router(core_router)
router.include_router(sourcing_router)
