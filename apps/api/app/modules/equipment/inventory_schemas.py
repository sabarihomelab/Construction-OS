from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.equipment.inventory_models import (
    StockDirection,
    StockLocationStatus,
    StockLocationType,
    StockSourceType,
    StockTransactionType,
)


class MaterialStockLocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    location_type: StockLocationType = StockLocationType.SITE_STORE
    description: str | None = Field(default=None, max_length=4000)


class MaterialStockLocationRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    code: str
    name: str
    location_type: StockLocationType
    status: StockLocationStatus
    description: str | None
    revision: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialStockTransactionRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    stock_location_id: UUID
    material_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    transaction_type: StockTransactionType
    direction: StockDirection
    quantity: Decimal
    unit_code: str
    occurred_at: datetime
    source_type: StockSourceType
    source_record_id: UUID
    source_parent_id: UUID | None
    source_reference: str | None
    unit_cost_snapshot: Decimal | None
    currency_code: str | None
    created_by_membership_id: UUID
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialStockBalanceRead(BaseModel):
    stock_location_id: UUID
    material_id: UUID
    unit_code: str
    quantity_on_hand: Decimal
