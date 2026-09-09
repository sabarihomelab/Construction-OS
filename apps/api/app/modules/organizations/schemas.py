from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.organizations.models import TimeFormat, UnitSystem


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=100)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class OrganizationRead(OrganizationCreate):
    id: UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class OrganizationSettingsCreate(BaseModel):
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    unit_system: UnitSystem = UnitSystem.METRIC
    time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR
    first_day_of_week: int = Field(default=1, ge=1, le=7)
    storage_quota_bytes: int | None = Field(default=None, gt=0)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class OrganizationSettingsRead(OrganizationSettingsCreate):
    organization_id: UUID
    settings_version: int
    model_config = ConfigDict(from_attributes=True)
