from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.equipment.consumption_models import MaterialConsumptionStatus


class MaterialConsumptionCreate(BaseModel):
    material_id: UUID
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    consumption_date: date
    quantity: Decimal = Field(gt=0)
    unit_code: str = Field(min_length=1, max_length=40)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    cost_basis: str | None = Field(default=None, max_length=120)
    source_reference: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)


class MaterialConsumptionPost(BaseModel):
    expected_revision: int = Field(ge=1)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    cost_basis: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=1000)


class MaterialConsumptionRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    material_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    consumption_date: date
    quantity: Decimal
    unit_code: str
    unit_cost: Decimal | None
    total_cost: Decimal | None
    currency_code: str
    cost_basis: str | None
    source_reference: str | None
    location: str | None
    notes: str | None
    status: MaterialConsumptionStatus
    revision: int
    created_by_membership_id: UUID
    posted_by_membership_id: UUID | None
    posted_at: datetime | None
    reversed_by_membership_id: UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
