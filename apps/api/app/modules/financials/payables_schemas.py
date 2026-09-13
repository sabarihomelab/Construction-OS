from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.financials.payables_models import (
    VendorBillMatchStatus,
    VendorBillStatus,
)


class VendorBillCreate(BaseModel):
    purchase_order_id: UUID
    supplier_invoice_number: str = Field(min_length=1, max_length=120)
    invoice_date: date
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class VendorBillReceiptMatchCreate(BaseModel):
    goods_receipt_line_id: UUID
    matched_quantity: Decimal = Field(gt=0)


class VendorBillLineCreate(BaseModel):
    purchase_order_line_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    hsn_sac: str | None = Field(default=None, max_length=16)
    tax_code: str | None = Field(default=None, max_length=40)
    tax_rate: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)
    receipt_matches: list[VendorBillReceiptMatchCreate] = Field(default_factory=list)


class VendorBillTransition(BaseModel):
    expected_revision: int = Field(ge=1)
    allow_variance_override: bool = False
    reason: str | None = Field(default=None, max_length=1000)


class VendorBillReceiptMatchRead(BaseModel):
    id: UUID
    vendor_bill_line_id: UUID
    goods_receipt_line_id: UUID
    matched_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


class VendorBillLineRead(BaseModel):
    id: UUID
    vendor_bill_id: UUID
    project_id: UUID
    line_number: int
    purchase_order_line_id: UUID
    material_id: UUID | None
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str
    unit_code: str
    quantity: Decimal
    unit_price: Decimal
    po_unit_price_snapshot: Decimal
    taxable_value: Decimal
    hsn_sac: str | None
    tax_code: str | None
    tax_rate: Decimal | None
    tax_amount: Decimal
    line_total: Decimal
    matched_quantity: Decimal
    quantity_variance: Decimal
    price_variance_amount: Decimal
    match_status: VendorBillMatchStatus
    receipt_matches: list[VendorBillReceiptMatchRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class VendorBillRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    bill_number: str
    supplier_party_id: UUID
    purchase_order_id: UUID
    supplier_invoice_number: str
    invoice_date: date
    due_date: date | None
    currency_code: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: VendorBillStatus
    match_status: VendorBillMatchStatus
    revision: int
    submitted_by_membership_id: UUID | None
    submitted_at: datetime | None
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    variance_override_by_membership_id: UUID | None
    variance_override_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorBillDetailRead(VendorBillRead):
    lines: list[VendorBillLineRead] = Field(default_factory=list)
