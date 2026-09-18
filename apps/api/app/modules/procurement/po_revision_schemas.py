from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.procurement.schemas import PurchaseOrderLineCreate


class PurchaseOrderAmendmentCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1, max_length=500)


class PurchaseOrderRevisionRead(BaseModel):
    purchase_order_id: UUID
    version_number: int
    organization_id: UUID
    project_id: UUID
    issued_at: datetime
    approved_by_membership_id: UUID | None
    snapshot_json: dict[str, object]
    superseded_reason: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
