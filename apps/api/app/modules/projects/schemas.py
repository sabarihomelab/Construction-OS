from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.models import ProjectStatus


class ProjectCreate(BaseModel):
    organization_id: UUID
    number: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    address: str | None = None


class ProjectRead(ProjectCreate):
    id: UUID
    status: ProjectStatus
    model_config = ConfigDict(from_attributes=True)
