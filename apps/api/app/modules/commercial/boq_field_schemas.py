from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BOQFieldReferenceRead(BaseModel):
    item_id: UUID
    boq_id: UUID
    boq_code: str
    boq_name: str
    boq_revision: int = Field(ge=1)
    wbs_code_id: UUID | None
    line_number: int = Field(ge=1)
    item_code: str
    description: str
    unit_code: str
    quantity: Decimal = Field(ge=0)
    item_revision: int = Field(ge=1)
