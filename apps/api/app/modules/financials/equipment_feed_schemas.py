from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EquipmentUsageCostPost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_cost_head_id: UUID
