from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.organizations.models import (
    INDIA_DEFAULT_CURRENCY,
    INDIA_DEFAULT_LOCALE,
    INDIA_DEFAULT_TIMEZONE,
    TimeFormat,
    UnitSystem,
)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=100)
    country_code: str | None = Field(default="IN", min_length=2, max_length=2)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class OrganizationRead(OrganizationCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrganizationProfileUpdate(BaseModel):
    expected_updated_at: datetime
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Company name cannot be blank")
        return normalized


class OrganizationSettingsCreate(BaseModel):
    locale: str = Field(default=INDIA_DEFAULT_LOCALE, min_length=2, max_length=35)
    timezone: str = Field(default=INDIA_DEFAULT_TIMEZONE, min_length=1, max_length=64)
    base_currency: str = Field(default=INDIA_DEFAULT_CURRENCY, min_length=3, max_length=3)
    unit_system: UnitSystem = UnitSystem.METRIC
    time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR
    first_day_of_week: int = Field(default=1, ge=1, le=7)
    storage_quota_bytes: int | None = Field(default=None, gt=0)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class OrganizationSettingsUpdate(BaseModel):
    expected_settings_version: int = Field(ge=1)
    locale: str | None = Field(default=None, min_length=2, max_length=35)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    unit_system: UnitSystem | None = None
    time_format: TimeFormat | None = None
    first_day_of_week: int | None = Field(default=None, ge=1, le=7)
    storage_quota_bytes: int | None = Field(default=None, gt=0)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class OrganizationSettingsRead(OrganizationSettingsCreate):
    organization_id: UUID
    settings_version: int
    model_config = ConfigDict(from_attributes=True)


class CompanyProfileRead(BaseModel):
    organization: OrganizationRead
    settings: OrganizationSettingsRead
