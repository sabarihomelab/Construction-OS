from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.procurement.models import (
    GoodsReceiptStatus,
    PurchaseOrderStatus,
    RequisitionStatus,
)


class RequisitionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    required_by: date | None = None
    notes: str | None = None


class RequisitionRead(BaseModel):
    id: UUID
    project_id: UUID
    number: str
    title: str
    requested_by_membership_id: UUID
    required_by: date | None
    status: RequisitionStatus
    revision: int
    submitted_at: datetime | None
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class RequisitionLineCreate(BaseModel):
    line_number: int = Field(ge=1)
    material_id: UUID | None = None
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    description: str = Field(min_length=1)
    unit_code: str = Field(min_length=1, max_length=24)
    quantity: Decimal = Field(gt=0)
    estimated_unit_rate: Decimal = Field(default=Decimal(0), ge=0)
    notes: str | None = None


class RequisitionLineRead(BaseModel):
    id: UUID
    requisition_id: UUID
    project_id: UUID
    line_number: int
    material_id: UUID | None
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str
    unit_code: str
    quantity: Decimal
    estimated_unit_rate: Decimal
    estimated_amount: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderCreate(BaseModel):
    supplier_party_id: UUID
    requisition_id: UUID | None = None
    order_date: date
    expected_delivery_date: date | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    notes: str | None = None


class PurchaseOrderRead(BaseModel):
    id: UUID
    project_id: UUID
    number: str
    supplier_party_id: UUID
    requisition_id: UUID | None
    status: PurchaseOrderStatus
    order_date: date
    expected_delivery_date: date | None
    currency_code: str
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderLineCreate(BaseModel):
    line_number: int = Field(ge=1)
    requisition_line_id: UUID | None = None
    material_id: UUID | None = None
    wbs_code_id: UUID | None = None
    description: str = Field(min_length=1)
    unit_code: str = Field(min_length=1, max_length=24)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    hsn_sac: str | None = Field(default=None, max_length=16)
    tax_code: str | None = Field(default=None, max_length=40)
    tax_rate: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class PurchaseOrderLineRead(BaseModel):
    id: UUID
    purchase_order_id: UUID
    project_id: UUID
    line_number: int
    requisition_line_id: UUID | None
    material_id: UUID | None
    wbs_code_id: UUID | None
    description: str
    unit_code: str
    quantity: Decimal
    unit_price: Decimal
    taxable_value: Decimal
    hsn_sac: str | None
    tax_code: str | None
    tax_rate: Decimal | None
    tax_amount: Decimal
    line_total: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: UUID
    stock_location_id: UUID | None = None
    received_at: datetime
    challan_number: str | None = Field(default=None, max_length=120)
    supplier_invoice_number: str | None = Field(default=None, max_length=120)
    delivered_by: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class GoodsReceiptRead(BaseModel):
    id: UUID
    project_id: UUID
    purchase_order_id: UUID
    stock_location_id: UUID | None
    number: str
    status: GoodsReceiptStatus
    received_at: datetime
    received_by_membership_id: UUID
    challan_number: str | None
    supplier_invoice_number: str | None
    delivered_by: str | None
    notes: str | None
    revision: int

    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptLineCreate(BaseModel):
    purchase_order_line_id: UUID
    received_quantity: Decimal = Field(gt=0)
    accepted_quantity: Decimal = Field(default=Decimal(0), ge=0)
    rejected_quantity: Decimal = Field(default=Decimal(0), ge=0)
    unit_code: str = Field(min_length=1, max_length=24)
    remarks: str | None = None


class GoodsReceiptLineRead(BaseModel):
    id: UUID
    goods_receipt_id: UUID
    project_id: UUID
    purchase_order_line_id: UUID
    received_quantity: Decimal
    accepted_quantity: Decimal
    rejected_quantity: Decimal
    unit_code: str
    remarks: str | None

    model_config = ConfigDict(from_attributes=True)


class RevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class GoodsReceiptReceiveAction(RevisionAction):
    stock_location_id: UUID | None = None
