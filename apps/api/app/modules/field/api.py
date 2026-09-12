from fastapi import APIRouter

from app.modules.field import dpr_report_type  # noqa: F401
from app.modules.field.dpr_generation_router import router as dpr_generation_router
from app.modules.field.dpr_offline_router import router as dpr_offline_router
from app.modules.field.dpr_photo_router import router as dpr_photo_router
from app.modules.field.dpr_reference_router import router as dpr_reference_router
from app.modules.field.dpr_router import router as dpr_router
from app.modules.field.router import router as daily_report_router

router = APIRouter()
router.include_router(daily_report_router)
router.include_router(dpr_offline_router)
router.include_router(dpr_reference_router)
router.include_router(dpr_router)
router.include_router(dpr_generation_router)
router.include_router(dpr_photo_router)
