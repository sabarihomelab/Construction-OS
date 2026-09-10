from uuid import UUID

from pydantic import BaseModel


class MaterialConsumptionCostPost(BaseModel):
    material_cost_head_id: UUID
