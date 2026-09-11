from fastapi import APIRouter

from app.modules.commercial.party_router import router as party_router
from app.modules.commercial.router import router as commercial_router
from app.modules.commercial.wbs_router import router as wbs_router

router = APIRouter()
router.routes.extend(
    route
    for route in commercial_router.routes
    if not getattr(route, "path", "").startswith("/projects/{project_id}/commercial/wbs")
)
router.include_router(party_router)
router.include_router(wbs_router)
