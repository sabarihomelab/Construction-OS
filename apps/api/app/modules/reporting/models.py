from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ReportVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class ReportRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReportOutputFormat(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"


class ViewVisibility(StrEnum):
    PRIVATE = "private"
    SHARED = "shared"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class SavedView(UUIDTimestampMixin, Base):
    __tablename__ = "saved_views"
    __table_args__ = (
        UniqueConstraint("organization_id", "owner_user_id", "name", "dataset_key", name="uq_saved_views_owner_name_dataset"),
        CheckConstraint("version >= 1", name="ck_saved_views_version"),
        Index("ix_saved_views_org_dataset", "organization_id", "dataset_key"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    dataset_key: Mapped[str] = mapped_column(String(140), index=True)
    name: Mapped[str] = mapped_column(String(180))
    visibility: Mapped[ViewVisibility] = mapped_column(Enum(ViewVisibility, native_enum=False, values_callable=enum_values), default=ViewVisibility.PRIVATE)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)


class ReportDefinition(UUIDTimestampMixin, Base):
    __tablename__ = "report_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_report_definitions_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_report_definitions_id_org"),
        CheckConstraint("current_version >= 0", name="ck_report_definitions_current_version"),
        Index("ix_report_definitions_org_dataset", "organization_id", "dataset_key"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_key: Mapped[str] = mapped_column(String(140), index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ReportDefinitionVersion(UUIDTimestampMixin, Base):
    __tablename__ = "report_definition_versions"
    __table_args__ = (
        ForeignKeyConstraint(["definition_id", "organization_id"], ["report_definitions.id", "report_definitions.organization_id"], name="fk_report_definition_versions_definition_org", ondelete="CASCADE"),
        UniqueConstraint("definition_id", "version", name="uq_report_definition_versions_version"),
        UniqueConstraint("id", "organization_id", name="uq_report_definition_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_report_definition_versions_version"),
        Index("ix_report_definition_versions_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    definition_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[ReportVersionStatus] = mapped_column(Enum(ReportVersionStatus, native_enum=False, values_callable=enum_values), default=ReportVersionStatus.DRAFT)
    query_spec: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    presentation_spec: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ReportRun(UUIDTimestampMixin, Base):
    __tablename__ = "report_runs"
    __table_args__ = (
        ForeignKeyConstraint(["report_version_id", "organization_id"], ["report_definition_versions.id", "report_definition_versions.organization_id"], name="fk_report_runs_version_org", ondelete="RESTRICT"),
        ForeignKeyConstraint(["output_file_asset_id", "organization_id"], ["file_assets.id", "file_assets.organization_id"], name="fk_report_runs_output_asset_org", ondelete="RESTRICT"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_report_runs_progress"),
        Index("ix_report_runs_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[ReportRunStatus] = mapped_column(Enum(ReportRunStatus, native_enum=False, values_callable=enum_values), default=ReportRunStatus.QUEUED)
    output_format: Mapped[ReportOutputFormat] = mapped_column(Enum(ReportOutputFormat, native_enum=False, values_callable=enum_values))
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    output_file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class DashboardDefinition(UUIDTimestampMixin, Base):
    __tablename__ = "dashboard_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_dashboard_definitions_org_key"),
        CheckConstraint("version >= 1", name="ck_dashboard_definitions_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(180))
    layout: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
