from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.offline.models import SyncMutationStatus
from app.modules.workforce.attendance_models import (
    AttendanceHistoryType,
    AttendanceMarkStatus,
    AttendanceRegisterStatus,
)
from app.modules.workforce.models import WorkerEngagementType


class AttendanceRegisterCreate(BaseModel):
    attendance_date: date
    shift_code: str = Field(default="day", min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=4000)
    populate_active_workers: bool = True


class AttendanceEntryWrite(BaseModel):
    assignment_id: UUID
    mark_status: AttendanceMarkStatus
    regular_hours: Decimal = Field(default=Decimal(0), ge=0, le=24)
    overtime_hours: Decimal = Field(default=Decimal(0), ge=0, le=24)
    wbs_code_id: UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_hours(self) -> "AttendanceEntryWrite":
        if self.regular_hours + self.overtime_hours > Decimal(24):
            raise ValueError("regular_hours + overtime_hours cannot exceed 24")
        if self.mark_status in {
            AttendanceMarkStatus.ABSENT,
            AttendanceMarkStatus.LEAVE,
            AttendanceMarkStatus.WEEKLY_OFF,
            AttendanceMarkStatus.NOT_MARKED,
        } and (self.regular_hours or self.overtime_hours):
            raise ValueError("non-working attendance marks cannot contain work hours")
        return self


class AttendanceEntriesWrite(BaseModel):
    expected_revision: int = Field(ge=1)
    entries: list[AttendanceEntryWrite] = Field(max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)


class AttendanceVersionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class AttendanceReject(AttendanceVersionAction):
    reason: str = Field(min_length=1, max_length=1000)


class AttendanceEntryRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    register_id: UUID
    assignment_id: UUID
    worker_id: UUID
    crew_id: UUID | None
    employer_party_id: UUID | None
    wbs_code_id: UUID | None
    engagement_type: WorkerEngagementType | None
    trade: str | None
    mark_status: AttendanceMarkStatus
    regular_hours: Decimal
    overtime_hours: Decimal
    location: str | None
    notes: str | None
    source_type: str
    source_id: str | None
    context_snapshot: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceRegisterRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    attendance_date: date
    shift_code: str
    status: AttendanceRegisterStatus
    revision: int
    prepared_by_membership_id: UUID
    approved_by_membership_id: UUID | None
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    notes: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceRegisterDetailRead(AttendanceRegisterRead):
    entries: list[AttendanceEntryRead] = Field(default_factory=list)


class AttendanceHistoryRead(BaseModel):
    id: UUID
    event_type: AttendanceHistoryType
    register_revision: int
    actor_user_id: UUID | None
    details: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceDPRSummaryRow(BaseModel):
    employer_party_id: UUID | None
    crew_id: UUID | None
    trade: str | None
    worker_count: int
    present_count: int
    absent_count: int
    regular_hours: Decimal
    overtime_hours: Decimal


class AttendanceDPRSummaryRead(BaseModel):
    register_id: UUID
    project_id: UUID
    attendance_date: date
    shift_code: str
    rows: list[AttendanceDPRSummaryRow]


class AttendanceOfflineOperation(StrEnum):
    CREATE_REGISTER = "create_register"
    REPLACE_ENTRIES = "replace_entries"
    SUBMIT = "submit"


class AttendanceOfflineMutationRequest(BaseModel):
    device_id: UUID
    client_mutation_id: UUID
    entity_id: UUID
    operation: AttendanceOfflineOperation
    base_revision: int | None = Field(default=None, ge=1)
    create: AttendanceRegisterCreate | None = None
    entries: AttendanceEntriesWrite | None = None
    action: AttendanceVersionAction | None = None

    @model_validator(mode="after")
    def validate_operation_payload(self) -> "AttendanceOfflineMutationRequest":
        supplied = sum(item is not None for item in (self.create, self.entries, self.action))
        if supplied != 1:
            raise ValueError("Exactly one Attendance operation payload is required")

        if self.operation == AttendanceOfflineOperation.CREATE_REGISTER:
            if self.create is None or self.base_revision is not None:
                raise ValueError("Create requires create payload and no base_revision")
        elif self.operation == AttendanceOfflineOperation.REPLACE_ENTRIES:
            if self.entries is None or self.base_revision is None:
                raise ValueError("Entry replacement requires entries payload and base_revision")
            if self.entries.expected_revision != self.base_revision:
                raise ValueError("entries.expected_revision must match base_revision")
        elif self.operation == AttendanceOfflineOperation.SUBMIT:
            if self.action is None or self.base_revision is None:
                raise ValueError("Submit requires action payload and base_revision")
            if self.action.expected_revision != self.base_revision:
                raise ValueError("action.expected_revision must match base_revision")
        return self


class AttendanceOfflineMutationResponse(BaseModel):
    client_mutation_id: UUID
    entity_id: UUID
    status: SyncMutationStatus
    replayed: bool
    server_revision: int | None = Field(default=None, ge=1)
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None
