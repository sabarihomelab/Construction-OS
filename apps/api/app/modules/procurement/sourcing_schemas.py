from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.procurement.models import PurchaseOrderStatus
from app.modules.procurement.sourcing_models import (
    RFQInvitationStatus,
    RFQStatus,
    VendorQuotationStatus,
)


class RFQCreate(BaseModel):
    requisition_id: UUID
    title: str = Field(min_length=1, max_length=255)
    due_at: datetime | None = None
    requisition_line_ids: list[UUID] | None = None
    notes: str | None = None


class RFQRead(BaseModel):
    id: UUID
    project_id: UUID
    requisition_id: UUID
    number: str
    title: str
    due_at: datetime | None
    status: RFQStatus
    revision: int
    issued_at: datetime | None
    closed_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class RFQLineRead(BaseModel):
    id: UUID
    project_id: UUID
    rfq_id: UUID
    requisition_line_id: UUID
    line_number: int
    material_id: UUID | None
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str
    unit_code: str
    quantity: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class RFQVendorInvite(BaseModel):
    supplier_party_id: UUID
    notes: str | None = None


class RFQVendorRead(BaseModel):
    id: UUID
    rfq_id: UUID
    project_id: UUID
    supplier_party_id: UUID
    status: RFQInvitationStatus
    invited_at: datetime
    responded_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class QuotationCreate(BaseModel):
    supplier_party_id: UUID
    supplier_reference: str | None = Field(default=None, max_length=120)
    quote_date: date
    valid_until: date | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    notes: str | None = None


class QuotationRead(BaseModel):
    id: UUID
    project_id: UUID
    rfq_id: UUID
    supplier_party_id: UUID
    number: str
    supplier_reference: str | None
    quote_date: date
    valid_until: date | None
    currency_code: str
    status: VendorQuotationStatus
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    revision: int
    submitted_at: datetime | None
    withdrawn_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class QuotationLineCreate(BaseModel):
    rfq_line_id: UUID
    line_number: int = Field(ge=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    hsn_sac: str | None = Field(default=None, max_length=16)
    tax_code: str | None = Field(default=None, max_length=40)
    tax_rate: Decimal | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    notes: str | None = None


class QuotationLineRead(BaseModel):
    id: UUID
    project_id: UUID
    quotation_id: UUID
    rfq_line_id: UUID
    line_number: int
    quantity: Decimal
    unit_code: str
    unit_price: Decimal
    taxable_value: Decimal
    hsn_sac: str | None
    tax_code: str | None
    tax_rate: Decimal | None
    tax_amount: Decimal
    line_total: Decimal
    lead_time_days: int | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class SourcingRevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class VendorSelectionCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    quotation_id: UUID
    reason: str | None = Field(default=None, max_length=2000)


class VendorSelectionRead(BaseModel):
    id: UUID
    rfq_id: UUID
    project_id: UUID
    quotation_id: UUID
    supplier_party_id: UUID
    selected_by_membership_id: UUID
    selected_at: datetime
    reason: str | None
    comparison_snapshot: dict
    supersedes_selection_id: UUID | None
    superseded_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RFQComparisonOfferRead(BaseModel):
    quotation_id: UUID
    supplier_party_id: UUID
    quotation_number: str
    currency_code: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal | None
    line_total: Decimal
    lead_time_days: int | None


class RFQComparisonLineRead(BaseModel):
    rfq_line_id: UUID
    line_number: int
    description: str
    unit_code: str
    required_quantity: Decimal
    offers: list[RFQComparisonOfferRead]


class RFQComparisonQuotationRead(BaseModel):
    quotation_id: UUID
    supplier_party_id: UUID
    quotation_number: str
    currency_code: str
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    covered_lines: int
    required_lines: int
    complete: bool


class RFQComparisonRead(BaseModel):
    rfq_id: UUID
    rfq_number: str
    rfq_revision: int
    lines: list[RFQComparisonLineRead]
    quotations: list[RFQComparisonQuotationRead]


class PurchaseOrderFromSelectionCreate(BaseModel):
    order_date: date
    expected_delivery_date: date | None = None
    notes: str | None = None


class PurchaseOrderSourceRead(BaseModel):
    id: UUID
    project_id: UUID
    purchase_order_id: UUID
    rfq_id: UUID
    quotation_id: UUID
    selection_id: UUID

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderFromSelectionRead(BaseModel):
    purchase_order_id: UUID
    purchase_order_number: str
    status: PurchaseOrderStatus
    revision: int
    source: PurchaseOrderSourceRead
