from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ConfigurationScopeType(StrEnum):
    COMPANY = "company"
    PROJECT_TEMPLATE = "project_template"
    PROJECT = "project"


class ConfigurationChangeClass(StrEnum):
    PRESENTATION = "presentation"
    METADATA = "metadata"
    BUSINESS_RULE = "business_rule"
    WORKFLOW = "workflow"
    FINANCIAL = "financial"
    SECURITY = "security"


class PreferenceContextType(StrEnum):
    COMPANY = "company"
    PROJECT = "project"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ConfigurationValue(UUIDTimestampMixin, Base):
    __tablename__ = "configuration_values"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "module_key",
            "configuration_key",
            "scope_type",
            "scope_id",
            name="uq_configuration_values_scope_key",
        ),
        UniqueConstraint("id", "organization_id", name="uq_configuration_values_id_org"),
        CheckConstraint("current_version >= 1", name="ck_configuration_values_current_version"),
        Index(
            "ix_configuration_values_resolution",
            "organization_id",
            "module_key",
            "scope_type",
            "scope_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    module_key: Mapped[str] = mapped_column(String(80), index=True)
    configuration_key: Mapped[str] = mapped_column(String(180), index=True)
    scope_type: Mapped[ConfigurationScopeType] = mapped_column(
        Enum(ConfigurationScopeType, native_enum=False, values_callable=enum_values),
        index=True,
    )
    scope_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ConfigurationValueVersion(UUIDTimestampMixin, Base):
    __tablename__ = "configuration_value_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["configuration_value_id", "organization_id"],
            ["configuration_values.id", "configuration_values.organization_id"],
            name="fk_configuration_value_versions_value_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "configuration_value_id",
            "version",
            name="uq_configuration_value_versions_value_version",
        ),
        CheckConstraint("version >= 1", name="ck_configuration_value_versions_version"),
        Index(
            "ix_configuration_value_versions_effective",
            "configuration_value_id",
            "effective_from",
            "version",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    configuration_value_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    change_class: Mapped[ConfigurationChangeClass] = mapped_column(
        Enum(ConfigurationChangeClass, native_enum=False, values_callable=enum_values)
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    changed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConfigurationScopeRevision(Base):
    __tablename__ = "configuration_scope_revisions"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_configuration_scope_revisions_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    module_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    scope_type: Mapped[ConfigurationScopeType] = mapped_column(
        Enum(ConfigurationScopeType, native_enum=False, values_callable=enum_values),
        primary_key=True,
    )
    scope_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MembershipPreferenceState(Base):
    __tablename__ = "membership_preference_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_membership_preference_states_membership_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("revision >= 1", name="ck_membership_preference_states_revision"),
    )

    membership_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MembershipPreference(UUIDTimestampMixin, Base):
    __tablename__ = "membership_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_membership_preferences_membership_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_membership_preferences_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "membership_id",
            "module_key",
            "preference_key",
            "context_type",
            "context_id",
            name="uq_membership_preferences_context_key",
        ),
        CheckConstraint("version >= 1", name="ck_membership_preferences_version"),
        CheckConstraint(
            "(context_type = 'company' AND project_id IS NULL AND context_id = organization_id) OR "
            "(context_type = 'project' AND project_id IS NOT NULL AND context_id = project_id)",
            name="ck_membership_preferences_context",
        ),
        Index(
            "ix_membership_preferences_resolution",
            "organization_id",
            "membership_id",
            "module_key",
            "context_type",
            "context_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    module_key: Mapped[str] = mapped_column(String(80), index=True)
    preference_key: Mapped[str] = mapped_column(String(180), index=True)
    context_type: Mapped[PreferenceContextType] = mapped_column(
        Enum(PreferenceContextType, native_enum=False, values_callable=enum_values)
    )
    context_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
