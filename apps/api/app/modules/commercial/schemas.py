from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.commercial.models import (
    BOQStatus,
    MeasurementStatus,
    PartyStatus,
    PartyType,
    ProjectPartyRole,
    RABillStatus,
    RecordStatus,
    WBSKind,
)


class PartyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    party_type: PartyType
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    pan: str | None = Field(default=None, min_length=10, max_length=10)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    locality: str | None = Field(default=None, max_length=120)
    state_name: str | None = Field(default=None, max_length=120)
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=12)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str | None = None

    @field_validator("code", "name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("gstin", "pan")
    @classmethod
    def uppercase_tax_ids(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class PartyUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    party_type: PartyType | None = None
    status: PartyStatus | None = None
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    pan: str | None = Field(default=None, min_length=10, max_length=10)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    locality: str | None = Field(default=None, max_length=120)
    state_name: str | None = Field(default=None, max_length=120)
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=12)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str | None = None
    reason: str | None = Field(default=None, max_length=1000)


class PartyRead(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    legal_name: str | None
    party_type: PartyType
    status: PartyStatus
    gstin: str | None
    pan: str | None
    email: str | None
    phone: str | None
    address_line_1: str | None
    address_line_2: str | None
    locality: str | None
    state_name: str | None
    state_code: str | None
    postal_code: str | None
    payment_terms_days: int | None
    notes: str | None
    revision: int
    model_config = ConfigDict(from_attributes=True)


class ProjectPartyAssignmentCreate(BaseModel):
    party_id: UUID
    role: ProjectPartyRole


class ProjectPartyAssignmentUpdate(BaseModel):
    expected_updated_at: datetime
    active: bool
    reason: str | None = Field(default=None, max_length=1000)


class ProjectPartyAssignmentRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    party_id: UUID
    role: ProjectPartyRole
    active: bool
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WBSCodeCreate(BaseModel):
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    kind: WBSKind = WBSKind.COST_CODE
    description: str | None = None


class WBSCodeUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    parent_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: WBSKind | None = None
    status: RecordStatus | None = None
    description: str | None = None
    reason: str | None = Field(default=None, max_length=1000)


class WBSCodeRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    parent_id: UUID | None
    code: str
    name: str
    kind: WBSKind
    status: RecordStatus
    description: str | None
    revision: int
    model_config = ConfigDict(from_attributes=True)


class BOQCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class BOQRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    code: str
    name: str
    description: str | None
    currency_code: str
    status: BOQStatus
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class BOQItemCreate(BaseModel):
    wbs_code_id: UUID | None = None
    line_number: int = Field(ge=1)
    item_code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    unit_code: str = Field(min_length=1, max_length=24)
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=3)
    rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    hsn_sac: str | None = Field(default=None, max_length=16)
    notes: str | None = None


class BOQItemUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    wbs_code_id: UUID | None = None
    description: str | None = Field(default=None, min_length=1)
    unit_code: str | None = Field(default=None, min_length=1, max_length=24)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    hsn_sac: str | None = Field(default=None, max_length=16)
    notes: str | None = None
    reason: str | None = Field(default=None, max_length=1000)


class BOQItemRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    boq_id: UUID
    wbs_code_id: UUID | None
    line_number: int
    item_code: str
    description: str
    unit_code: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    hsn_sac: str | None
    notes: str | None
    revision: int
    model_config = ConfigDict(from_attributes=True)


class BOQDetailRead(BOQRead):
    items: list[BOQItemRead]
    total_amount: Decimal


class RevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class MeasurementCreate(BaseModel):
    boq_item_id: UUID
    measurement_date: date
    location: str | None = Field(default=None, max_length=255)
    description: str | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class MeasurementRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    boq_item_id: UUID
    entry_number: int
    measurement_date: date
    location: str | None
    description: str | None
    quantity: Decimal
    unit_code: str
    status: MeasurementStatus
    recorded_by_membership_id: UUID
    certified_by_membership_id: UUID | None
    certified_at: datetime | None
    revision: int
    model_config = ConfigDict(from_attributes=True)


class MeasurementReview(BaseModel):
    expected_revision: int = Field(ge=1)
    approve: bool = True
    reason: str | None = Field(default=None, max_length=1000)


class RABillCreate(BaseModel):
    counterparty_id: UUID
    bill_number: str = Field(min_length=1, max_length=80)
    period_start: date
    period_end: date
    retention_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    statutory_deduction_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    other_deduction_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "RABillCreate":
        if self.period_end < self.period_start:
            raise ValueError("RA bill period end cannot be before period start")
        return self


class RABillLineRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    ra_bill_id: UUID
    boq_item_id: UUID
    current_quantity: Decimal
    rate: Decimal
    gross_amount: Decimal
    model_config = ConfigDict(from_attributes=True)


class RABillRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    counterparty_id: UUID
    bill_number: str
    period_start: date
    period_end: date
    status: RABillStatus
    currency_code: str
    gross_amount: Decimal
    retention_amount: Decimal
    statutory_deduction_amount: Decimal
    other_deduction_amount: Decimal
    net_payable: Decimal
    revision: int
    submitted_at: datetime | None
    certified_by_membership_id: UUID | None
    certified_at: datetime | None
    notes: str | None
    model_config = ConfigDict(from_attributes=True)


class RABillDetailRead(RABillRead):
    lines: list[RABillLineRead]


class CommercialDashboardRead(BaseModel):
    project_id: UUID
    boq_value: Decimal
    measured_value: Decimal
    certified_measurement_value: Decimal
    submitted_bill_value: Decimal
    certified_bill_value: Decimal
    open_measurements: int
    draft_bills: int
