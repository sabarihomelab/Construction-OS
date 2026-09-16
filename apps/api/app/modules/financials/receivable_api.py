from fastapi import APIRouter

from app.modules.financials.governed_receivable_router import router as governed_router
from app.modules.financials.receivable_router import router as legacy_router


router = APIRouter()
router.routes.extend(
    route
    for route in legacy_router.routes
    if getattr(route, "path", "")
    != "/projects/{project_id}/financials/receivables/invoices/from-ra-bill"
)
router.include_router(governed_router)
