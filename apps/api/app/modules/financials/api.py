from fastapi import APIRouter

from app.modules.financials.accounting_export_router import router as accounting_export_router
from app.modules.financials.attachment_router import router as attachment_router
from app.modules.financials.budget_control_router import router as budget_control_router
from app.modules.financials.commercial_control_router import router as commercial_control_router
from app.modules.financials.commitment_router import router as commitment_router
from app.modules.financials.equipment_feed_router import router as equipment_feed_router
from app.modules.financials.feed_router import router as feed_router
from app.modules.financials.mapping_router import router as mapping_router
from app.modules.financials.material_feed_router import router as material_feed_router
from app.modules.financials.payables_router import router as payables_router
from app.modules.financials.receivable_api import router as receivable_router
from app.modules.financials.router import router as core_router
from app.modules.financials.subcontract_feed_router import router as subcontract_feed_router
from app.modules.financials.subcontract_payable_router import router as subcontract_payable_router

router = APIRouter()
router.include_router(accounting_export_router)
router.include_router(attachment_router)
router.include_router(core_router)
router.include_router(mapping_router)
router.include_router(feed_router)
router.include_router(material_feed_router)
router.include_router(equipment_feed_router)
router.include_router(subcontract_feed_router)
router.include_router(subcontract_payable_router)
router.include_router(commitment_router)
router.include_router(commercial_control_router)
router.include_router(budget_control_router)
router.include_router(payables_router)
router.include_router(receivable_router)
