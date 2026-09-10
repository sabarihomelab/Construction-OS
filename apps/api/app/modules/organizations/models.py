from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin

INDIA_DEFAULT_LOCALE = "en-IN"
INDIA_DEFAULT_TIMEZONE = "Asia/Kolkata"
INDIA_DEFAULT_CURRENCY = "INR"


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"
    MIXED = "mixed"


class TimeFormat(StrEnum):
    TWELVE_HOUR = "12h"
    TWENTY_FOUR_HOUR = "24h"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Organization(UUIDTimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    locale: Mapped[str] = mapped_column(String(35), default=INDIA_DEFAULT_LOCALE)
    timezone: Mapped[str] = mapped_column(String(64), default=INDIA_DEFAULT_TIMEZONE)
    base_currency: Mapped[str] = mapped_column(String(3), default=INDIA_DEFAULT_CURRENCY)
    unit_system: Mapped[UnitSystem] = mapped_column(
        Enum(UnitSystem, native_enum=False, values_callable=enum_values), default=UnitSystem.METRIC
    )
    time_format: Mapped[TimeFormat] = mapped_column(
        Enum(TimeFormat, native_enum=False, values_callable=enum_values),
        default=TimeFormat.TWENTY_FOUR_HOUR,
    )
    first_day_of_week: Mapped[int] = mapped_column(Integer, default=1)
    settings_version: Mapped[int] = mapped_column(Integer, default=1)
    storage_quota_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
