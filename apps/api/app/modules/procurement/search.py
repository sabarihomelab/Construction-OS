from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.procurement.models import GoodsReceipt, PurchaseOrder, PurchaseRequisition
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def requisition_search_projection(db: AsyncSession, organization_id: UUID, entity_id: str) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(select(PurchaseRequisition).where(PurchaseRequisition.id == row_id, PurchaseRequisition.organization_id == organization_id))
    if row is None:
        return None
    return SearchProjection(entity_type="purchase_requisition", entity_id=str(row.id), entity_version=row.revision, required_permission_key="procurement.requisition.view", scope_type="project", scope_id=str(row.project_id), title=row.title, subtitle=row.number, body=row.notes or "", keywords=[row.number, row.status.value], route_hint=f"/projects/{row.project_id}/procurement/requisitions/{row.id}", source_updated_at=row.updated_at)


async def purchase_order_search_projection(db: AsyncSession, organization_id: UUID, entity_id: str) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == row_id, PurchaseOrder.organization_id == organization_id))
    if row is None:
        return None
    return SearchProjection(entity_type="purchase_order", entity_id=str(row.id), entity_version=row.revision, required_permission_key="procurement.purchase_order.view", scope_type="project", scope_id=str(row.project_id), title=f"Purchase Order {row.number}", subtitle=row.status.value, body=row.notes or "", keywords=[row.number, row.status.value, row.currency_code], route_hint=f"/projects/{row.project_id}/procurement/purchase-orders/{row.id}", source_updated_at=row.updated_at)


async def goods_receipt_search_projection(db: AsyncSession, organization_id: UUID, entity_id: str) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(select(GoodsReceipt).where(GoodsReceipt.id == row_id, GoodsReceipt.organization_id == organization_id))
    if row is None:
        return None
    return SearchProjection(entity_type="goods_receipt", entity_id=str(row.id), entity_version=row.revision, required_permission_key="procurement.receipt.view", scope_type="project", scope_id=str(row.project_id), title=f"Goods Receipt {row.number}", subtitle=row.status.value, body=row.notes or "", keywords=[row.number, row.status.value, row.challan_number or "", row.supplier_invoice_number or ""], route_hint=f"/projects/{row.project_id}/procurement/goods-receipts/{row.id}", source_updated_at=row.updated_at)


for entity_type, provider in (("purchase_requisition", requisition_search_projection), ("purchase_order", purchase_order_search_projection), ("goods_receipt", goods_receipt_search_projection)):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
