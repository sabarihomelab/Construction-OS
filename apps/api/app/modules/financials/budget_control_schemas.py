from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.modules.estimating.models import BudgetCategory


class BudgetCommercialControlLine(BaseModel):
    wbs_code_id: UUID
    wbs_code: str
    wbs_name: str
    category: BudgetCategory
    has_budget_line: bool
    budget_amount: Decimal
    committed_amount: Decimal
    actual_cost: Decimal
    forecast_exposure: Decimal
    uncommitted_budget: Decimal
    commitment_remaining: Decimal
    budget_remaining_to_actual: Decimal
    forecast_variance: Decimal


class BudgetCommercialControlSummary(BaseModel):
    project_id: UUID
    budget_id: UUID
    budget_code: str
    budget_revision: int
    budget_approved_at: datetime | None
    currency_code: str
    control_coverage_complete: bool
    total_budget_amount: Decimal
    total_committed_amount: Decimal
    total_actual_cost: Decimal
    total_forecast_exposure: Decimal
    total_uncommitted_budget: Decimal
    total_commitment_remaining: Decimal
    total_budget_remaining_to_actual: Decimal
    total_forecast_variance: Decimal
    unallocated_commitment_amount: Decimal
    unallocated_actual_cost: Decimal
    lines: list[BudgetCommercialControlLine]
