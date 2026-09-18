from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FinancialAttachmentCreate(BaseModel):
    asset_id: UUID


class FinancialAttachmentRead(BaseModel):
    link_id: UUID
    asset_id: UUID
    asset_name: str
    asset_current_version: int
    pinned_version: int
    relation_type: str
    created_at: datetime
