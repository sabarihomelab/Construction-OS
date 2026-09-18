from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.safety.models import (
    CorrectiveActionStatus,
    InspectionResultStatus,
    InspectionRunStatus,
    InspectionTemplateVersionStatus,
    PunchItemStatus,
    PunchPriority,
    SafetyRecordStatus,
    SafetyRecordType,
    SafetySeverity,
)


class SafetyRecordCreate(BaseModel):
    record_type: SafetyRecordType
    severity: SafetySeverity = SafetySeverity.MEDIUM
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=20000)
    location: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None


class SafetyRecordUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    severity: SafetySeverity | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=20000)
    location: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    status: SafetyRecordStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class SafetyRecordRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    number: int
    record_type: SafetyRecordType
    status: SafetyRecordStatus
    severity: SafetySeverity
    title: str
    description: str
    location: str | None
    occurred_at: datetime | None
    reported_by_membership_id: UUID
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    revision: int
    closed_at: datetime | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CorrectiveActionCreate(BaseModel):
    description: str = Field(min_length=1, max_length=10000)
    assigned_to_membership_id: UUID | None = None
    due_date: date | None = None


class CorrectiveActionUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    assigned_to_membership_id: UUID | None = None
    due_date: date | None = None
    status: CorrectiveActionStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class CorrectiveActionRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    safety_record_id: UUID
    sequence: int
    description: str
    assigned_to_membership_id: UUID | None
    due_date: date | None
    status: CorrectiveActionStatus
    revision: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InspectionTemplateCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)


class InspectionTemplateRead(BaseModel):
    id: UUID
    organization_id: UUID
    key: str
    name: str
    description: str | None
    active: bool
    current_version: int
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InspectionChecklistItem(BaseModel):
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    label: str = Field(min_length=1, max_length=500)
    required: bool = True
    response_type: str = Field(default="pass_fail_na", max_length=40)
    help_text: str | None = Field(default=None, max_length=2000)


class InspectionTemplateVersionCreate(BaseModel):
    checklist: list[InspectionChecklistItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_item_keys(self) -> "InspectionTemplateVersionCreate":
        keys = [item.key for item in self.checklist]
        if len(keys) != len(set(keys)):
            raise ValueError("inspection checklist item keys must be unique")
        return self


class InspectionTemplateVersionUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    checklist: list[InspectionChecklistItem] = Field(min_length=1, max_length=500)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_unique_item_keys(self) -> "InspectionTemplateVersionUpdate":
        keys = [item.key for item in self.checklist]
        if len(keys) != len(set(keys)):
            raise ValueError("inspection checklist item keys must be unique")
        return self


class InspectionTemplateVersionRead(BaseModel):
    id: UUID
    organization_id: UUID
    template_id: UUID
    version: int
    status: InspectionTemplateVersionStatus
    checklist: list[dict[str, object]]
    revision: int
    effective_from: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InspectionRunCreate(BaseModel):
    template_version_id: UUID
    title: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class InspectionResultWrite(BaseModel):
    item_key: str = Field(min_length=1, max_length=160)
    result: InspectionResultStatus = InspectionResultStatus.NOT_CHECKED
    value: object | None = None
    comment: str | None = Field(default=None, max_length=10000)


class InspectionResultsWrite(BaseModel):
    expected_revision: int = Field(ge=1)
    results: list[InspectionResultWrite] = Field(default_factory=list, max_length=500)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_unique_result_keys(self) -> "InspectionResultsWrite":
        keys = [item.item_key for item in self.results]
        if len(keys) != len(set(keys)):
            raise ValueError("inspection result item keys must be unique")
        return self


class InspectionResultRead(InspectionResultWrite):
    id: UUID
    organization_id: UUID
    inspection_run_id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InspectionRunRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    number: int
    template_version_id: UUID
    inspector_membership_id: UUID
    status: InspectionRunStatus
    title: str
    location: str | None
    revision: int
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    started_at: datetime | None
    submitted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InspectionRunDetailRead(InspectionRunRead):
    results: list[InspectionResultRead] = Field(default_factory=list)


class VersionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class RejectAction(VersionAction):
    reason: str = Field(min_length=1, max_length=1000)


class PunchItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=255)
    priority: PunchPriority = PunchPriority.MEDIUM
    assigned_to_membership_id: UUID | None = None
    due_date: date | None = None
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=160)


class PunchItemUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=255)
    priority: PunchPriority | None = None
    assigned_to_membership_id: UUID | None = None
    due_date: date | None = None
    status: PunchItemStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class PunchItemRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    number: int
    title: str
    description: str | None
    location: str | None
    priority: PunchPriority
    status: PunchItemStatus
    assigned_to_membership_id: UUID | None
    due_date: date | None
    source_type: str | None
    source_id: str | None
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    revision: int
    completed_at: datetime | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
