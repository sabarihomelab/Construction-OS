from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class CustomFieldType(StrEnum):
    TEXT = "text"
    LONG_TEXT = "long_text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    CURRENCY = "currency"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    USER = "user"
    COMPANY = "company"
    PROJECT = "project"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    ATTACHMENT = "attachment"
    MEASUREMENT = "measurement"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class CustomFieldDefinition(UUIDTimestampMixin, Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "entity_type",
            "key",
            name="uq_custom_field_definitions_org_entity_key",
        ),
        CheckConstraint("version >= 1", name="ck_custom_field_definitions_version"),
        CheckConstraint("display_order >= 0", name="ck_custom_field_definitions_display_order"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_type: Mapped[CustomFieldType] = mapped_column(
        Enum(CustomFieldType, native_enum=False, values_callable=enum_values)
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    validation_rules: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    searchable: Mapped[bool] = mapped_column(Boolean, default=False)
    filterable: Mapped[bool] = mapped_column(Boolean, default=False)
    reportable: Mapped[bool] = mapped_column(Boolean, default=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    editable: Mapped[bool] = mapped_column(Boolean, default=True)
    view_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True
    )
    edit_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class CustomFieldOption(UUIDTimestampMixin, Base):
    __tablename__ = "custom_field_options"
    __table_args__ = (
        UniqueConstraint(
            "definition_id", "key", name="uq_custom_field_options_definition_key"
        ),
        CheckConstraint("version >= 1", name="ck_custom_field_options_version"),
        CheckConstraint("display_order >= 0", name="ck_custom_field_options_display_order"),
    )

    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(160))
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class CustomFieldDefinitionRevision(Base):
    __tablename__ = "custom_field_definition_revisions"

    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    changed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomFieldValue(UUIDTimestampMixin, Base):
    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "definition_id",
            "entity_id",
            name="uq_custom_field_values_org_definition_entity",
        ),
        CheckConstraint("definition_version >= 1", name="ck_custom_field_values_definition_version"),
        Index("ix_custom_field_values_org_entity", "organization_id", "entity_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    definition_version: Mapped[int] = mapped_column(Integer)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    date_value: Mapped[date | None] = mapped_column(Date, nullable=True)
    datetime_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uuid_value: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    json_value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
