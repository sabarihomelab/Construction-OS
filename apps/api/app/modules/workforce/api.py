from fastapi import APIRouter

from app.modules.workforce.attendance_router import router as attendance_router
from app.modules.workforce.management_router import router as management_router
from app.modules.workforce.router import router as core_router

router = APIRouter()
router.include_router(core_router)
router.include_router(management_router)
router.include_router(attendance_router)
