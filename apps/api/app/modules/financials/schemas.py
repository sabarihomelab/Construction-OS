from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.financials.job_cost_models import (
    CostHeadCategory,
    ProjectCostSourceType,
    ProjectCostStatus,
    SiteCashAccountStatus,
    SiteCashDirection,
    SiteCashTransactionType,
    SiteExpenseStatus,
)
from app.modules.financials.models import AccountType, RecordStatus


class CostHeadCreate(BaseModel):
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category: CostHeadCategory
    allows_posting: bool = True
    description: str | None = Field(default=None, max_length=4000)


class CostHeadUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    parent_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: RecordStatus | None = None
    allows_posting: bool | None = None
    description: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class CostHeadRead(BaseModel):
    id: UUID
    organization_id: UUID
    parent_id: UUID | None
    code: str
    name: str
    category: CostHeadCategory
    status: RecordStatus
    allows_posting: bool
    description: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LedgerAccountCreate(BaseModel):
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    account_type: AccountType
    allows_posting: bool = True
    description: str | None = Field(default=None, max_length=4000)


class LedgerAccountRead(BaseModel):
    id: UUID
    organization_id: UUID
    parent_id: UUID | None
    code: str
    name: str
    account_type: AccountType
    status: RecordStatus
    allows_posting: bool
    revision: int
    description: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CostHeadLedgerMappingCreate(BaseModel):
    ledger_account_id: UUID
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CostHeadLedgerMappingCreate":
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class SiteCashAccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    custodian_worker_id: UUID | None = None
    custodian_membership_id: UUID | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=4000)


class SiteCashAccountRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    code: str
    name: str
    custodian_worker_id: UUID | None
    custodian_membership_id: UUID | None
    status: SiteCashAccountStatus
    currency_code: str
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SiteCashAdvanceCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    transaction_date: date
    source_reference: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=500)


class SiteCashTransactionRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    cash_account_id: UUID
    transaction_number: str
    transaction_date: date
    transaction_type: SiteCashTransactionType
    direction: SiteCashDirection
    amount: Decimal
    source_expense_id: UUID | None
    source_reference: str | None
    description: str | None
    posted_by_membership_id: UUID
    posted_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SiteCashBalanceRead(BaseModel):
    cash_account_id: UUID
    currency_code: str
    inflow: Decimal
    outflow: Decimal
    balance: Decimal


class SiteExpenseAllocationWrite(BaseModel):
    cost_head_id: UUID
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)


class SiteExpenseCreate(BaseModel):
    expense_date: date
    cash_account_id: UUID | None = None
    paid_to_party_id: UUID | None = None
    description: str = Field(min_length=1, max_length=500)
    gross_amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=80)
    payment_reference: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=4000)
    allocations: list[SiteExpenseAllocationWrite] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_allocation_total(self) -> "SiteExpenseCreate":
        allocated = sum((item.amount for item in self.allocations), Decimal(0))
        if allocated != self.gross_amount:
            raise ValueError("site expense allocation total must equal gross_amount")
        return self


class SiteExpenseAllocationRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    expense_id: UUID
    line_number: int
    cost_head_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str | None
    amount: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SiteExpenseRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    expense_number: str
    expense_date: date
    cash_account_id: UUID | None
    paid_to_party_id: UUID | None
    description: str
    gross_amount: Decimal
    currency_code: str
    payment_method: str | None
    payment_reference: str | None
    status: SiteExpenseStatus
    configuration_context: dict[str, object]
    revision: int
    submitted_by_membership_id: UUID | None
    submitted_at: datetime | None
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    posted_by_membership_id: UUID | None
    posted_at: datetime | None
    rejection_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SiteExpenseDetailRead(SiteExpenseRead):
    allocations: list[SiteExpenseAllocationRead] = Field(default_factory=list)


class RevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class RejectAction(RevisionAction):
    reason: str = Field(min_length=1, max_length=1000)


class ProjectCostAllocationRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    cost_entry_id: UUID
    line_number: int
    cost_head_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    party_id: UUID | None
    worker_assignment_id: UUID | None
    equipment_asset_id: UUID | None
    material_id: UUID | None
    description: str | None
    quantity: Decimal | None
    unit_code: str | None
    amount: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectCostRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    entry_number: str
    entry_date: date
    source_type: ProjectCostSourceType
    source_id: UUID | None
    source_reference: str | None
    description: str
    total_amount: Decimal
    currency_code: str
    status: ProjectCostStatus
    revision: int
    posted_by_membership_id: UUID | None
    posted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JobCostSummaryLine(BaseModel):
    cost_head_id: UUID
    cost_head_code: str
    cost_head_name: str
    category: CostHeadCategory
    amount: Decimal


class JobCostSummaryRead(BaseModel):
    project_id: UUID
    currency_code: str
    total_actual_cost: Decimal
    by_cost_head: list[JobCostSummaryLine]
