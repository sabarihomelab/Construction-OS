from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.scheduling.models import ActivityStatus, DependencyType, ScheduleStatus


class ScheduleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    data_date: date | None = None
    notes: str | None = None


class ScheduleUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    data_date: date | None = None
    notes: str | None = None
    reason: str | None = None


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    code: str
    name: str
    description: str | None
    status: ScheduleStatus
    revision: int
    active_baseline_version: int | None
    data_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ActivityCreate(BaseModel):
    activity_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    wbs_code_id: UUID | None = None
    responsible_membership_id: UUID | None = None
    planned_start: date
    planned_finish: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.planned_finish < self.planned_start:
            raise ValueError("planned_finish must be on or after planned_start")
        return self


class ActivityUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    wbs_code_id: UUID | None = None
    responsible_membership_id: UUID | None = None
    planned_start: date | None = None
    planned_finish: date | None = None
    status: ActivityStatus | None = None
    notes: str | None = None
    reason: str | None = None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    schedule_id: UUID
    activity_code: str
    name: str
    description: str | None
    wbs_code_id: UUID | None
    responsible_membership_id: UUID | None
    planned_start: date
    planned_finish: date
    actual_start: date | None
    actual_finish: date | None
    percent_complete: Decimal
    status: ActivityStatus
    revision: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DependencyCreate(BaseModel):
    predecessor_activity_id: UUID
    successor_activity_id: UUID
    dependency_type: DependencyType = DependencyType.FINISH_START
    lag_days: int = Field(default=0, ge=-3650, le=3650)


class DependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID
    predecessor_activity_id: UUID
    successor_activity_id: UUID
    dependency_type: DependencyType
    lag_days: int


class BaselineCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = None


class BaselineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID
    version_number: int
    created_by_membership_id: UUID
    reason: str | None
    snapshot: dict
    created_at: datetime


class ProgressCreate(BaseModel):
    expected_activity_revision: int = Field(ge=1)
    data_date: date
    percent_complete: Decimal = Field(ge=0, le=100)
    actual_start: date | None = None
    actual_finish: date | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def validate_actual_dates(self):
        if self.actual_start and self.actual_finish and self.actual_finish < self.actual_start:
            raise ValueError("actual_finish must be on or after actual_start")
        if self.percent_complete == 100 and self.actual_finish is None:
            raise ValueError("actual_finish is required when percent_complete is 100")
        return self


class ProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID
    activity_id: UUID
    data_date: date
    percent_complete: Decimal
    actual_start: date | None
    actual_finish: date | None
    recorded_by_membership_id: UUID
    recorded_at: datetime
    remarks: str | None


class ScheduleSummary(BaseModel):
    schedule: ScheduleRead
    activity_count: int
    completed_activity_count: int
    average_percent_complete: Decimal
    baseline_version: int | None
