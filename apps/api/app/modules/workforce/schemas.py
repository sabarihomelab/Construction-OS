from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.workforce.models import EmploymentStatus


class EmployeeCreate(BaseModel):
    organization_id: UUID
    employee_number: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None


class EmployeeRead(EmployeeCreate):
    id: UUID
    status: EmploymentStatus
    model_config = ConfigDict(from_attributes=True)


class CrewCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=120)
    supervisor_employee_id: UUID | None = None


class CrewRead(CrewCreate):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
