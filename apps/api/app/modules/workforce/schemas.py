from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.workforce.models import (
    CrewStatus,
    EmploymentStatus,
    ProjectWorkerAssignmentStatus,
    TimecardHistoryType,
    TimecardStatus,
)


class WorkerCreate(BaseModel):
    worker_number: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=160)
    trade: str | None = Field(default=None, max_length=120)
    classification: str | None = Field(default=None, max_length=120)
    hire_date: date | None = None
    organization_membership_id: UUID | None = None


class WorkerUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    worker_number: str | None = Field(default=None, min_length=1, max_length=64)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=160)
    trade: str | None = Field(default=None, max_length=120)
    classification: str | None = Field(default=None, max_length=120)
    hire_date: date | None = None
    termination_date: date | None = None
    status: EmploymentStatus | None = None
    organization_membership_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self) -> "WorkerUpdate":
        if self.hire_date and self.termination_date and self.termination_date < self.hire_date:
            raise ValueError("termination_date cannot be before hire_date")
        return self


class WorkerRead(BaseModel):
    id: UUID
    organization_id: UUID
    worker_number: str
    first_name: str
    last_name: str
    preferred_name: str | None
    email: str | None
    phone: str | None
    job_title: str | None
    trade: str | None
    classification: str | None
    hire_date: date | None
    termination_date: date | None
    status: EmploymentStatus
    organization_membership_id: UUID | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CrewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    supervisor_worker_id: UUID | None = None


class CrewUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    supervisor_worker_id: UUID | None = None
    status: CrewStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class CrewRead(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    supervisor_worker_id: UUID | None
    status: CrewStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CrewMembershipCreate(BaseModel):
    worker_id: UUID
    role: str | None = Field(default=None, max_length=120)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CrewMembershipCreate":
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class CrewMembershipEnd(BaseModel):
    expected_revision: int = Field(ge=1)
    effective_to: date
    reason: str | None = Field(default=None, max_length=1000)


class CrewMembershipRead(BaseModel):
    id: UUID
    organization_id: UUID
    crew_id: UUID
    worker_id: UUID
    role: str | None
    effective_from: date
    effective_to: date | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectWorkerAssignmentCreate(BaseModel):
    worker_id: UUID
    crew_id: UUID | None = None
    project_role: str | None = Field(default=None, max_length=160)
    trade: str | None = Field(default=None, max_length=120)
    default_cost_code: str | None = Field(default=None, max_length=80)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectWorkerAssignmentCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ProjectWorkerAssignmentUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    crew_id: UUID | None = None
    project_role: str | None = Field(default=None, max_length=160)
    trade: str | None = Field(default=None, max_length=120)
    default_cost_code: str | None = Field(default=None, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectWorkerAssignmentStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectWorkerAssignmentUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ProjectWorkerAssignmentRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    worker_id: UUID
    crew_id: UUID | None
    status: ProjectWorkerAssignmentStatus
    project_role: str | None
    trade: str | None
    default_cost_code: str | None
    start_date: date | None
    end_date: date | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TimeEntryWrite(BaseModel):
    work_date: date
    regular_hours: Decimal = Field(default=Decimal("0"), ge=0, le=24)
    overtime_hours: Decimal = Field(default=Decimal("0"), ge=0, le=24)
    double_time_hours: Decimal = Field(default=Decimal("0"), ge=0, le=24)
    cost_code: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=255)
    work_description: str | None = Field(default=None, max_length=4000)
    source_type: str = Field(default="manual", min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_total_hours(self) -> "TimeEntryWrite":
        total = self.regular_hours + self.overtime_hours + self.double_time_hours
        if total > Decimal("24"):
            raise ValueError("total daily hours cannot exceed 24")
        return self


class TimeEntryRead(TimeEntryWrite):
    id: UUID
    organization_id: UUID
    timecard_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TimecardCreate(BaseModel):
    worker_id: UUID
    week_start: date


class TimecardEntriesWrite(BaseModel):
    expected_revision: int = Field(ge=1)
    entries: list[TimeEntryWrite] = Field(default_factory=list, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)


class TimecardVersionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class TimecardReject(TimecardVersionAction):
    reason: str = Field(min_length=1, max_length=1000)


class TimecardRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    worker_id: UUID
    week_start: date
    status: TimecardStatus
    revision: int
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    voided_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TimecardDetailRead(TimecardRead):
    entries: list[TimeEntryRead] = Field(default_factory=list)


class TimecardHistoryRead(BaseModel):
    id: UUID
    event_type: TimecardHistoryType
    timecard_revision: int
    actor_user_id: UUID | None
    details: dict[str, object]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
