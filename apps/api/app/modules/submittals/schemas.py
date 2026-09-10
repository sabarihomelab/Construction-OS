from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.submittals.models import (
    SubmittalHistoryType,
    SubmittalReferenceType,
    SubmittalReviewDecision,
    SubmittalRevisionStatus,
    SubmittalStatus,
)


class SubmittalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    submittal_type: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    required_on_site_date: date | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    ball_in_court_membership_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank")
        return value


class SubmittalUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    submittal_type: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    required_on_site_date: date | None = None
    lead_time_days: int | None = Field(default=None, ge=0)


class SubmittalVersionAction(BaseModel):
    expected_version: int = Field(ge=1)


class SubmittalBallInCourtUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    membership_id: UUID | None = None


class SubmittalRevisionCreate(BaseModel):
    revision_label: str = Field(min_length=1, max_length=80)
    description: str | None = None

    @field_validator("revision_label")
    @classmethod
    def strip_revision_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Revision label cannot be blank")
        return value


class SubmittalRevisionSubmit(BaseModel):
    reviewer_membership_id: UUID


class SubmittalReviewCreate(BaseModel):
    decision: SubmittalReviewDecision
    comments: str | None = None
    official: bool = False


class SubmittalReferenceCreate(BaseModel):
    reference_type: SubmittalReferenceType
    reference_id: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=255)


class SubmittalVoidRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class SubmittalRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    number: int
    title: str
    description: str | None
    submittal_type: str | None
    status: SubmittalStatus
    due_date: date | None
    required_on_site_date: date | None
    lead_time_days: int | None
    ball_in_court_membership_id: UUID | None
    latest_decision: SubmittalReviewDecision | None
    current_revision_sequence: int
    version: int
    opened_at: datetime | None
    closed_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmittalRevisionRead(BaseModel):
    id: UUID
    organization_id: UUID
    submittal_id: UUID
    sequence: int
    revision_label: str
    description: str | None
    status: SubmittalRevisionStatus
    submitted_by_user_id: UUID | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmittalReviewRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    submittal_revision_id: UUID
    sequence: int
    reviewer_membership_id: UUID
    decision: SubmittalReviewDecision
    comments: str | None
    official: bool
    reviewed_at: datetime
    reviewed_by_user_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmittalReferenceRead(BaseModel):
    id: UUID
    organization_id: UUID
    submittal_id: UUID
    reference_type: SubmittalReferenceType
    reference_id: str
    label: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmittalHistoryRead(BaseModel):
    id: UUID
    organization_id: UUID
    submittal_id: UUID
    event_type: SubmittalHistoryType
    entity_version: int
    actor_user_id: UUID | None
    summary: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
