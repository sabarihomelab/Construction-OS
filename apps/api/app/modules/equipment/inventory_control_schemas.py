from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.equipment.inventory_models import StockTransactionType
from app.modules.equipment.inventory_schemas import MaterialStockTransactionRead


class ManualStockTransactionCreate(BaseModel):
    client_transaction_id: UUID
    stock_location_id: UUID
    material_id: UUID
    transaction_type: StockTransactionType
    quantity: Decimal = Field(gt=0)
    occurred_at: datetime
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    related_transaction_id: UUID | None = None
    source_reference: str | None = Field(default=None, max_length=160)
    unit_cost_snapshot: Decimal | None = Field(default=None, ge=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    reason: str = Field(min_length=3, max_length=2000)


class StockTransferCreate(BaseModel):
    client_transfer_id: UUID
    from_stock_location_id: UUID
    to_stock_location_id: UUID
    material_id: UUID
    quantity: Decimal = Field(gt=0)
    occurred_at: datetime
    source_reference: str | None = Field(default=None, max_length=160)
    unit_cost_snapshot: Decimal | None = Field(default=None, ge=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    reason: str = Field(min_length=3, max_length=2000)


class StockTransferRead(BaseModel):
    transfer_id: UUID
    outflow: MaterialStockTransactionRead
    inflow: MaterialStockTransactionRead
