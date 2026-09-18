from uuid import UUID

from pydantic import BaseModel


class SubcontractClaimCostPost(BaseModel):
    subcontract_cost_head_id: UUID
