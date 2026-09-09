from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = None
    timezone: str = "UTC"
    currency: str = Field(default="USD", min_length=3, max_length=3)


class OrganizationRead(OrganizationCreate):
    id: UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
