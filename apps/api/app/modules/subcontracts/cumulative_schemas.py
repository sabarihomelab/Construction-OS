from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.modules.subcontracts.models import SubcontractClaimStatus


class SubcontractClaimCumulativeLine(BaseModel):
    subcontract_line_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    line_number: int
    description: str
    unit_code: str
    contract_quantity: Decimal
    contract_rate: Decimal
    contract_amount: Decimal
    previous_certified_quantity: Decimal
    previous_certified_amount: Decimal
    current_claimed_quantity: Decimal
    current_gross_amount: Decimal
    current_certified_quantity: Decimal
    current_certified_amount: Decimal
    cumulative_certified_quantity: Decimal
    cumulative_certified_amount: Decimal
    remaining_quantity: Decimal
    remaining_amount: Decimal


class SubcontractClaimCumulativeRead(BaseModel):
    project_id: UUID
    subcontract_id: UUID
    claim_id: UUID
    claim_number: str
    claim_status: SubcontractClaimStatus
    currency_code: str
    previous_certified_gross: Decimal
    current_gross_amount: Decimal
    current_certified_gross: Decimal
    cumulative_certified_gross: Decimal
    current_retention_amount: Decimal
    current_other_deductions: Decimal
    current_tax_withheld_amount: Decimal
    current_net_certified: Decimal
    current_paid_amount: Decimal
    cumulative_paid_amount: Decimal
    lines: list[SubcontractClaimCumulativeLine]
