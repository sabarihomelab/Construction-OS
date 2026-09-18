from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.subcontracts.models import SubcontractClaimStatus


class SubcontractPayableLineRead(BaseModel):
    claim_line_id: UUID
    subcontract_line_id: UUID
    measurement_entry_id: UUID | None
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    description: str
    unit_code: str
    certified_quantity: Decimal
    rate: Decimal
    certified_amount: Decimal


class SubcontractPayableRead(BaseModel):
    claim_id: UUID
    claim_number: str
    subcontract_id: UUID
    subcontract_number: str
    contractor_party_id: UUID
    period_from: date
    period_to: date
    status: SubcontractClaimStatus
    currency_code: str
    gross_certified_work: Decimal
    retention_amount: Decimal
    other_deductions: Decimal
    tax_withheld_amount: Decimal
    net_certified_payable: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    certified_at: datetime
    lines: list[SubcontractPayableLineRead] = Field(default_factory=list)
