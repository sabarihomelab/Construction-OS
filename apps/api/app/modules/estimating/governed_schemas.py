import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.estimating.models import BudgetCategory, BudgetStatus, EstimateStatus
from app.modules.estimating.schemas import (
    BudgetLineRead,
    BudgetRead,
    EstimateItemRead,
    EstimateRead,
    RateAnalysisRead,
)


class EstimateDetailRead(EstimateRead):
    items: list[EstimateItemRead] = []
    item_count: int
    total_selling_amount: Decimal
    approval_snapshot_count: int


class EstimateCopyBOQRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class EstimateRevisionRequest(BaseModel):
    new_code: str = Field(min_length=1, max_length=64)
    new_name: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=1000)


class ApprovalSnapshotRead(BaseModel):
    id: UUID
    version_number: int
    approved_by_membership_id: UUID
    approved_at: datetime
    reason: str | None
    snapshot: dict[str, Any]

    @classmethod
    def from_row(cls, row: Any) -> "ApprovalSnapshotRead":
        return cls(
            id=row.id,
            version_number=row.version_number,
            approved_by_membership_id=row.approved_by_membership_id,
            approved_at=row.approved_at,
            reason=row.reason,
            snapshot=json.loads(row.snapshot_json),
        )


class RateAnalysisDetailRead(RateAnalysisRead):
    base_rate: Decimal
    wastage_amount: Decimal
    overhead_amount: Decimal
    cost_rate: Decimal
    profit_amount: Decimal
    selling_rate: Decimal


class BudgetDetailRead(BudgetRead):
    lines: list[BudgetLineRead] = []
    line_count: int
    total_amount: Decimal
    approval_snapshot_count: int


class EstimateSummaryRead(BaseModel):
    id: UUID
    code: str
    name: str
    status: EstimateStatus
    currency_code: str
    source_boq_id: UUID | None
    revision: int
    approved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class BudgetSummaryRead(BaseModel):
    id: UUID
    code: str
    name: str
    status: BudgetStatus
    currency_code: str
    estimate_id: UUID | None
    revision: int
    approved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class BudgetCategoryTotalRead(BaseModel):
    category: BudgetCategory
    amount: Decimal
