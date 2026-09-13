from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.identity.models import MembershipKind, MembershipStatus, UserStatus


class UserCreate(BaseModel):
    primary_email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    identity_provider: str | None = Field(default=None, max_length=64)
    identity_subject: str | None = Field(default=None, max_length=255)

    @field_validator("primary_email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        return str(value).strip().lower()


class UserRead(BaseModel):
    id: UUID
    primary_email: str
    display_name: str
    status: UserStatus
    is_active: bool
    last_authenticated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class UserPreferenceWrite(BaseModel):
    locale: str | None = Field(default=None, min_length=2, max_length=35)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    time_format: str | None = Field(default=None, pattern=r"^(12h|24h)$")
    date_format: str | None = Field(default=None, max_length=32)
    number_format: str | None = Field(default=None, max_length=32)


class MembershipCreate(BaseModel):
    organization_id: UUID
    user_id: UUID
    kind: MembershipKind = MembershipKind.INTERNAL
    status: MembershipStatus = MembershipStatus.INVITED


class MembershipRead(MembershipCreate):
    id: UUID
    joined_at: datetime | None
    ended_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
