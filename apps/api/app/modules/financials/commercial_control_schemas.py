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
    committed_amount: Decimal
    actual_cost: Decimal
    uncommitted_budget: Decimal
    commitment_remaining: Decimal
    budget_remaining: Decimal


class BOQCommercialControlSummary(BaseModel):
    project_id: UUID
    currency_code: str
    total_boq_amount: Decimal
    total_committed_amount: Decimal
    total_actual_cost: Decimal
    total_uncommitted_budget: Decimal
    total_commitment_remaining: Decimal
    total_budget_remaining: Decimal
    lines: list[BOQCommercialControlLine]
