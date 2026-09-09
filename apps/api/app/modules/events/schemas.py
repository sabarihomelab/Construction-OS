from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RealtimeEventRead(BaseModel):
    id: UUID
    sequence: int = Field(ge=1)
    event_type: str
    event_schema_version: int = Field(ge=1)
    entity_type: str
    entity_id: str | None
    entity_version: int | None
    scope_type: str | None
    scope_id: str | None
    payload: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RealtimeEventBatch(BaseModel):
    next_cursor: int = Field(ge=0)
    events: list[RealtimeEventRead]
