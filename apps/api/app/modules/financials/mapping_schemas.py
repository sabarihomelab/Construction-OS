from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CostHeadLedgerMappingRead(BaseModel):
    id: UUID
    organization_id: UUID
    cost_head_id: UUID
    ledger_account_id: UUID
    effective_from: date
    effective_to: date | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CostHeadLedgerMappingEnd(BaseModel):
    expected_revision: int = Field(ge=1)
    effective_to: date
    reason: str | None = Field(default=None, max_length=1000)
