from uuid import UUID

from pydantic import BaseModel


class EquipmentUsageCostPost(BaseModel):
    equipment_cost_head_id: UUID
