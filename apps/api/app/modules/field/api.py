from fastapi import APIRouter

from app.modules.field.dpr_router import router as dpr_router
from app.modules.field.router import router as daily_report_router

router = APIRouter()
router.include_router(daily_report_router)
router.include_router(dpr_router)
