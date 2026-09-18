from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.subcontracts.models import SubcontractClaimStatus, SubcontractStatus


class SubcontractCreate(BaseModel):
    contractor_party_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    start_date: date | None = None
    end_date: date | None = None
    retention_percent: Decimal = Field(default=Decimal(0), ge=0)
    notes: str | None = None


class SubcontractRead(BaseModel):
    id: UUID
    project_id: UUID
    number: str
    contractor_party_id: UUID
    title: str
    description: str | None
    currency_code: str
    status: SubcontractStatus
    start_date: date | None
    end_date: date | None
    original_amount: Decimal
    retention_percent: Decimal
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class SubcontractLineCreate(BaseModel):
    line_number: int = Field(ge=1)
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    description: str = Field(min_length=1)
    unit_code: str = Field(min_length=1, max_length=24)
    quantity: Decimal = Field(ge=0)
    rate: Decimal = Field(ge=0)
    notes: str | None = None


class SubcontractLineRead(BaseModel):
    id: UUID
    subcontract_id: UUID
    project_id: UUID
    line_number: int
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str
    unit_code: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class SubcontractClaimCreate(BaseModel):
    subcontract_id: UUID
    period_from: date
    period_to: date
    notes: str | None = None


class SubcontractClaimRead(BaseModel):
    id: UUID
    project_id: UUID
    subcontract_id: UUID
    number: str
    period_from: date
    period_to: date
    status: SubcontractClaimStatus
    gross_amount: Decimal
    retention_amount: Decimal
    other_deductions: Decimal
    tax_withheld_amount: Decimal
    certified_amount: Decimal
    paid_amount: Decimal
    submitted_by_membership_id: UUID | None
    submitted_at: datetime | None
    certified_by_membership_id: UUID | None
    certified_at: datetime | None
    revision: int
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class SubcontractClaimLineCreate(BaseModel):
    subcontract_line_id: UUID
    measurement_entry_id: UUID | None = None
    claimed_quantity: Decimal = Field(ge=0)
    remarks: str | None = None


class SubcontractClaimLineRead(BaseModel):
    id: UUID
    claim_id: UUID
    project_id: UUID
    subcontract_line_id: UUID
    measurement_entry_id: UUID | None
    claimed_quantity: Decimal
    certified_quantity: Decimal
    rate: Decimal
    gross_amount: Decimal
    certified_amount: Decimal
    remarks: str | None

    model_config = ConfigDict(from_attributes=True)


class RevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class ClaimCertification(BaseModel):
    expected_revision: int = Field(ge=1)
    other_deductions: Decimal = Field(default=Decimal(0), ge=0)
    tax_withheld_amount: Decimal = Field(default=Decimal(0), ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class ClaimPayment(BaseModel):
    expected_revision: int = Field(ge=1)
    paid_amount: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=1000)
