from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.field.models import ApprovalStatus


class TimeEntryCreate(BaseModel):
    organization_id: UUID
    project_id: UUID
    employee_id: UUID
    work_date: date
    regular_hours: float = Field(default=0, ge=0, le=24)
    overtime_hours: float = Field(default=0, ge=0, le=24)
    cost_code: str | None = None
    notes: str | None = None


class TimeEntryRead(TimeEntryCreate):
    id: UUID
    status: ApprovalStatus
    model_config = ConfigDict(from_attributes=True)


class DailyLogCreate(BaseModel):
    organization_id: UUID
    project_id: UUID
    report_date: date
    superintendent_employee_id: UUID | None = None
    work_completed: str = Field(min_length=1)
    delays: str | None = None
    safety_notes: str | None = None
    weather_summary: str | None = None


class DailyLogRead(DailyLogCreate):
    id: UUID
    status: ApprovalStatus
    model_config = ConfigDict(from_attributes=True)
