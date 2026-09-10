from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.estimating.models import (
    BudgetCategory,
    BudgetStatus,
    EstimateStatus,
    RateComponentKind,
)


class EstimateCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    source_boq_id: UUID | None = None


class EstimateRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    source_boq_id: UUID | None
    code: str
    name: str
    description: str | None
    currency_code: str
    status: EstimateStatus
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class EstimateItemCreate(BaseModel):
    line_number: int = Field(ge=1)
    item_code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    unit_code: str = Field(min_length=1, max_length=24)
    quantity: Decimal = Field(ge=0)
    rate: Decimal = Field(ge=0)
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    notes: str | None = None


class EstimateItemRead(BaseModel):
    id: UUID
    project_id: UUID
    estimate_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    line_number: int
    item_code: str
    description: str
    unit_code: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    notes: str | None
    revision: int

    model_config = ConfigDict(from_attributes=True)


class RateComponentCreate(BaseModel):
    kind: RateComponentKind
    description: str = Field(min_length=1, max_length=255)
    unit_code: str | None = Field(default=None, max_length=24)
    quantity: Decimal = Field(default=Decimal(1), ge=0)
    unit_rate: Decimal = Field(default=Decimal(0), ge=0)
    source_entity_type: str | None = Field(default=None, max_length=80)
    source_entity_id: UUID | None = None


class RateAnalysisCreate(BaseModel):
    estimate_item_id: UUID
    wastage_percent: Decimal = Field(default=Decimal(0), ge=0)
    overhead_percent: Decimal = Field(default=Decimal(0), ge=0)
    profit_percent: Decimal = Field(default=Decimal(0), ge=0)
    notes: str | None = None
    components: list[RateComponentCreate] = Field(min_length=1)


class RateComponentRead(BaseModel):
    id: UUID
    kind: RateComponentKind
    description: str
    unit_code: str | None
    quantity: Decimal
    unit_rate: Decimal
    amount: Decimal
    source_entity_type: str | None
    source_entity_id: UUID | None

    model_config = ConfigDict(from_attributes=True)


class RateAnalysisRead(BaseModel):
    id: UUID
    project_id: UUID
    estimate_item_id: UUID
    version_number: int
    wastage_percent: Decimal
    overhead_percent: Decimal
    profit_percent: Decimal
    calculated_rate: Decimal
    is_current: bool
    notes: str | None
    components: list[RateComponentRead] = []

    model_config = ConfigDict(from_attributes=True)


class BudgetCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    estimate_id: UUID | None = None
    notes: str | None = None


class BudgetRead(BaseModel):
    id: UUID
    project_id: UUID
    estimate_id: UUID | None
    code: str
    name: str
    currency_code: str
    status: BudgetStatus
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class BudgetLineCreate(BaseModel):
    wbs_code_id: UUID
    category: BudgetCategory
    amount: Decimal = Field(ge=0)
    notes: str | None = None


class BudgetLineRead(BaseModel):
    id: UUID
    budget_id: UUID
    project_id: UUID
    wbs_code_id: UUID
    category: BudgetCategory
    amount: Decimal
    notes: str | None
    revision: int

    model_config = ConfigDict(from_attributes=True)


class RevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)
