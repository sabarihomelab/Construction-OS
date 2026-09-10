from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.projects.models import ProjectMembershipStatus, ProjectStatus


class ProjectCreate(BaseModel):
    number: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    unit_system: str | None = Field(default=None, max_length=16)
    start_date: date | None = None
    target_completion_date: date | None = None
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    locality: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("number", "name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class ProjectUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    number: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    timezone: str | None = Field(default=None, max_length=64)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    unit_system: str | None = Field(default=None, max_length=16)
    start_date: date | None = None
    target_completion_date: date | None = None
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    locality: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    reason: str | None = Field(default=None, max_length=1000)


class ProjectRead(BaseModel):
    id: UUID
    organization_id: UUID
    number: str
    name: str
    description: str | None
    status: ProjectStatus
    revision: int
    configuration_template_version_id: UUID | None = None
    timezone: str | None
    currency_code: str | None
    unit_system: str | None
    start_date: date | None
    target_completion_date: date | None
    address_line_1: str | None
    address_line_2: str | None
    locality: str | None
    region: str | None
    postal_code: str | None
    country_code: str | None

    model_config = ConfigDict(from_attributes=True)


class ProjectMembershipCreate(BaseModel):
    organization_membership_id: UUID
    title: str | None = Field(default=None, max_length=160)


class ProjectMembershipStatusUpdate(BaseModel):
    status: ProjectMembershipStatus
    reason: str | None = Field(default=None, max_length=1000)


class ProjectMembershipRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    organization_membership_id: UUID
    status: ProjectMembershipStatus
    title: str | None

    model_config = ConfigDict(from_attributes=True)


class ProjectRoleAssignmentCreate(BaseModel):
    role_id: UUID


class ProjectRoleAssignmentRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_membership_id: UUID
    role_id: UUID

    model_config = ConfigDict(from_attributes=True)
