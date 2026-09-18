from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.meetings.models import (
    AgendaItemStatus,
    AttendanceStatus,
    MeetingActionStatus,
    MeetingHistoryType,
    MeetingReferenceType,
    MeetingStatus,
)


class MeetingSeriesCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    default_location: str | None = Field(default=None, max_length=255)
    recurrence_rule: str | None = Field(default=None, max_length=500)


class MeetingSeriesUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    default_location: str | None = Field(default=None, max_length=255)
    recurrence_rule: str | None = Field(default=None, max_length=500)
    active: bool | None = None
    reason: str | None = Field(default=None, max_length=1000)


class MeetingSeriesRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    category: str | None
    default_location: str | None
    recurrence_rule: str | None
    active: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MeetingCreate(BaseModel):
    series_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    start_at: datetime
    end_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_time_range(self) -> "MeetingCreate":
        if self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at cannot be before start_at")
        return self


class MeetingUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    status: MeetingStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class MeetingMinutesUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    minutes: str = Field(max_length=50000)
    reason: str | None = Field(default=None, max_length=1000)


class MeetingVersionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class MeetingRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    number: int
    series_id: UUID | None
    title: str
    category: str | None
    start_at: datetime
    end_at: datetime | None
    location: str | None
    status: MeetingStatus
    organizer_membership_id: UUID
    minutes: str | None
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    revision: int
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MeetingAttendeeCreate(BaseModel):
    membership_id: UUID | None = None
    external_name: str | None = Field(default=None, max_length=255)
    external_email: str | None = Field(default=None, max_length=320)
    role: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_identity(self) -> "MeetingAttendeeCreate":
        if self.membership_id is None and not (self.external_name or "").strip():
            raise ValueError("membership_id or external_name is required")
        return self


class MeetingAttendeeUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    attendance_status: AttendanceStatus | None = None
    role: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=1000)


class MeetingAttendeeRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    meeting_id: UUID
    membership_id: UUID | None
    external_name: str | None
    external_email: str | None
    role: str | None
    attendance_status: AttendanceStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AgendaItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    owner_membership_id: UUID | None = None


class AgendaItemUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    owner_membership_id: UUID | None = None
    status: AgendaItemStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class AgendaItemRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    meeting_id: UUID
    sequence: int
    title: str
    description: str | None
    owner_membership_id: UUID | None
    status: AgendaItemStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MeetingActionCreate(BaseModel):
    description: str = Field(min_length=1, max_length=10000)
    assignee_membership_id: UUID | None = None
    due_at: datetime | None = None


class MeetingActionUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    assignee_membership_id: UUID | None = None
    due_at: datetime | None = None
    status: MeetingActionStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class MeetingActionRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    meeting_id: UUID
    sequence: int
    description: str
    assignee_membership_id: UUID | None
    due_at: datetime | None
    status: MeetingActionStatus
    revision: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MeetingReferenceCreate(BaseModel):
    reference_type: MeetingReferenceType
    reference_id: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=255)


class MeetingReferenceRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    meeting_id: UUID
    reference_type: MeetingReferenceType
    reference_id: str
    label: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MeetingHistoryRead(BaseModel):
    id: UUID
    event_type: MeetingHistoryType
    meeting_revision: int
    actor_user_id: UUID | None
    details: dict[str, object]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
