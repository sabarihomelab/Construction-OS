from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class BOQCommercialControlLine(BaseModel):
    boq_item_id: UUID
    boq_id: UUID
    wbs_code_id: UUID | None
    line_number: int
    item_code: str
    description: str
    unit_code: str
    boq_quantity: Decimal
    boq_rate: Decimal
    boq_amount: Decimal
    approved_estimate_amount: Decimal | None
    committed_amount: Decimal
    actual_cost: Decimal
    certified_billed_amount: Decimal
    uncommitted_estimate: Decimal | None
    commitment_remaining: Decimal
    estimate_remaining: Decimal | None
    unbilled_boq_value: Decimal


class BOQCommercialControlSummary(BaseModel):
    project_id: UUID
    currency_code: str
    estimate_coverage_complete: bool
    total_boq_amount: Decimal
    total_approved_estimate_amount: Decimal
    total_committed_amount: Decimal
    total_actual_cost: Decimal
    total_certified_billed_amount: Decimal
    total_uncommitted_estimate: Decimal
    total_commitment_remaining: Decimal
    total_estimate_remaining: Decimal
    total_unbilled_boq_value: Decimal
    lines: list[BOQCommercialControlLine]
