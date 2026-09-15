from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.commercial.models import WBSKind


class DPRWorkProgressWBSReferenceRead(BaseModel):
    id: UUID
    code: str
    name: str
    kind: WBSKind
    parent_id: UUID | None

    model_config = ConfigDict(from_attributes=True)


class DPRWorkProgressBOQItemReferenceRead(BaseModel):
    id: UUID
    boq_id: UUID
    boq_code: str
    boq_name: str
    wbs_code_id: UUID | None
    item_code: str
    description: str
    unit_code: str


class DPRWorkProgressReferenceRead(BaseModel):
    wbs_codes: list[DPRWorkProgressWBSReferenceRead] = Field(default_factory=list)
    boq_items: list[DPRWorkProgressBOQItemReferenceRead] = Field(default_factory=list)
