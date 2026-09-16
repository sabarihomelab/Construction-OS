from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.financials.models import ClientInvoiceStatus, ClientReceiptStatus


class ClientInvoiceFromRABillCreate(BaseModel):
    source_ra_bill_id: UUID
    invoice_date: date
    due_date: date | None = None
    tax_code: str | None = Field(default=None, max_length=40)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, max_digits=9, decimal_places=4)
    withholding_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)


class ClientInvoiceLineRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    invoice_id: UUID
    line_number: int
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str
    unit_code: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    hsn_sac: str | None
    tax_code: str | None
    tax_rate: Decimal
    tax_amount: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClientInvoiceRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    invoice_number: str
    client_party_id: UUID
    source_ra_bill_id: UUID | None
    invoice_date: date
    due_date: date | None
    currency_code: str
    subtotal: Decimal
    tax_amount: Decimal
    withholding_amount: Decimal
    total_amount: Decimal
    net_receivable: Decimal
    status: ClientInvoiceStatus
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClientInvoiceDetailRead(ClientInvoiceRead):
    lines: list[ClientInvoiceLineRead] = Field(default_factory=list)
    received_amount: Decimal = Decimal("0.00")
    outstanding_amount: Decimal = Decimal("0.00")


class ClientInvoiceRevisionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class ClientReceiptAllocationCreate(BaseModel):
    invoice_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)


class ClientReceiptCreate(BaseModel):
    client_party_id: UUID
    receipt_date: date
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=80)
    payment_reference: str | None = Field(default=None, max_length=160)
    allocations: list[ClientReceiptAllocationCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_allocation_total(self) -> "ClientReceiptCreate":
        total = sum((item.amount for item in self.allocations), Decimal("0"))
        if total != self.amount:
            raise ValueError("receipt allocation total must equal receipt amount")
        if len({item.invoice_id for item in self.allocations}) != len(self.allocations):
            raise ValueError("receipt cannot allocate the same invoice more than once")
        return self


class ClientReceiptAllocationRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    receipt_id: UUID
    invoice_id: UUID
    amount: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClientReceiptRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    receipt_number: str
    client_party_id: UUID
    receipt_date: date
    amount: Decimal
    currency_code: str
    payment_method: str | None
    payment_reference: str | None
    status: ClientReceiptStatus
    posted_by_membership_id: UUID
    posted_at: datetime
    reversal_of_receipt_id: UUID | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClientReceiptDetailRead(ClientReceiptRead):
    allocations: list[ClientReceiptAllocationRead] = Field(default_factory=list)
