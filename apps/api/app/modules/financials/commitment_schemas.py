from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.financials.models import CommitmentSourceType, CommitmentStatus


class ProjectCommitmentAllocationRead(BaseModel):
    id: UUID
    line_number: int
    source_line_id: UUID
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    material_id: UUID | None
    description: str
    quantity: Decimal
    unit_code: str
    committed_amount: Decimal
    tax_amount: Decimal
    gross_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProjectCommitmentRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    source_type: CommitmentSourceType
    source_id: UUID
    source_number: str
    party_id: UUID
    wbs_code_id: UUID | None
    committed_amount: Decimal
    currency_code: str
    status: CommitmentStatus
    committed_at: datetime
    closed_at: datetime | None
    revision: int

    model_config = ConfigDict(from_attributes=True)


class ProjectCommitmentDetailRead(ProjectCommitmentRead):
    allocations: list[ProjectCommitmentAllocationRead]
