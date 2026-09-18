from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class TemplateVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class SetupRunStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    READY = "ready"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfigurationHealthStatus(StrEnum):
    HEALTHY = "healthy"
    ATTENTION = "attention"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ConfigurationTemplate(UUIDTimestampMixin, Base):
    __tablename__ = "configuration_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_configuration_templates_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_configuration_templates_id_org"),
        CheckConstraint("current_version >= 0", name="ck_configuration_templates_current_version"),
        Index("ix_configuration_templates_org_target", "organization_id", "target_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ConfigurationTemplateVersion(UUIDTimestampMixin, Base):
    __tablename__ = "configuration_template_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["configuration_templates.id", "configuration_templates.organization_id"],
            name="fk_configuration_template_versions_template_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "template_id", "version", name="uq_configuration_template_versions_template_version"
        ),
        UniqueConstraint("id", "organization_id", name="uq_configuration_template_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_configuration_template_versions_version"),
        Index("ix_configuration_template_versions_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    template_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[TemplateVersionStatus] = mapped_column(
        Enum(TemplateVersionStatus, native_enum=False, values_callable=enum_values),
        default=TemplateVersionStatus.DRAFT,
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SetupRun(UUIDTimestampMixin, Base):
    __tablename__ = "setup_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_version_id", "organization_id"],
            ["configuration_template_versions.id", "configuration_template_versions.organization_id"],
            name="fk_setup_runs_template_version_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="ck_setup_runs_revision"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_setup_runs_progress"),
        Index("ix_setup_runs_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    setup_type: Mapped[str] = mapped_column(String(80), index=True)
    target_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    template_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[SetupRunStatus] = mapped_column(
        Enum(SetupRunStatus, native_enum=False, values_callable=enum_values),
        default=SetupRunStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(120), nullable=True)
    validation_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    initiated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfigurationHealthCheck(UUIDTimestampMixin, Base):
    __tablename__ = "configuration_health_checks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "check_key",
            "target_type",
            "target_id",
            name="uq_configuration_health_checks_target",
        ),
        Index("ix_configuration_health_checks_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    check_key: Mapped[str] = mapped_column(String(140))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(160), default="organization")
    status: Mapped[ConfigurationHealthStatus] = mapped_column(
        Enum(ConfigurationHealthStatus, native_enum=False, values_callable=enum_values)
    )
    summary: Mapped[str] = mapped_column(String(255))
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
