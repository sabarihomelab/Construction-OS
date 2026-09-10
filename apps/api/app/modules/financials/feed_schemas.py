from uuid import UUID

from pydantic import BaseModel


class LabourTimeCostPost(BaseModel):
    labour_cost_head_id: UUID
