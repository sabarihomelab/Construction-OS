from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.rfis.models import (
    RFIHistoryType,
    RFIReferenceType,
    RFIResponseStatus,
    RFIStatus,
)


class RFICreate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=20000)
    due_date: date | None = None
    priority: str | None = Field(default=None, max_length=40)
    ball_in_court_membership_id: UUID | None = None

    @field_validator("subject", "question")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class RFIUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    question: str | None = Field(default=None, min_length=1, max_length=20000)
    due_date: date | None = None
    priority: str | None = Field(default=None, max_length=40)


class RFIVersionAction(BaseModel):
    expected_version: int = Field(ge=1)


class RFIBallInCourtUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    membership_id: UUID | None = None


class RFIResponseCreate(BaseModel):
    response_text: str = Field(min_length=1, max_length=40000)
    official: bool = False

    @field_validator("response_text")
    @classmethod
    def strip_response(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Response cannot be blank")
        return value


class RFIReferenceCreate(BaseModel):
    reference_type: RFIReferenceType
    reference_id: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=255)


class RFIVoidRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class RFIRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    number: int
    subject: str
    question: str
    status: RFIStatus
    priority: str | None
    due_date: date | None
    ball_in_court_membership_id: UUID | None
    version: int
    opened_at: datetime | None
    answered_at: datetime | None
    closed_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RFIResponseRead(BaseModel):
    id: UUID
    organization_id: UUID
    rfi_id: UUID
    sequence: int
    response_text: str
    status: RFIResponseStatus
    responded_by_user_id: UUID | None
    responded_at: datetime
    official_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RFIReferenceRead(BaseModel):
    id: UUID
    organization_id: UUID
    rfi_id: UUID
    reference_type: RFIReferenceType
    reference_id: str
    label: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RFIHistoryRead(BaseModel):
    id: UUID
    organization_id: UUID
    rfi_id: UUID
    event_type: RFIHistoryType
    entity_version: int
    actor_user_id: UUID | None
    summary: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
