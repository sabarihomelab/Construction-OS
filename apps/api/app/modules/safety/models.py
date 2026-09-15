from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
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


class SafetyRecordType(StrEnum):
    HAZARD = "hazard"
    OBSERVATION = "observation"
    INCIDENT = "incident"
    NEAR_MISS = "near_miss"
    TOOLBOX_TALK = "toolbox_talk"


class SafetyRecordStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    CLOSED = "closed"
    VOID = "void"


class SafetySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CorrectiveActionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InspectionTemplateVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class InspectionRunStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    VOID = "void"


class InspectionResultStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class PunchItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    CLOSED = "closed"
    VOID = "void"


class PunchPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class SafetyProjectCounter(Base):
    __tablename__ = "safety_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_safety_counter_project_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("next_record_number >= 1", name="ck_safety_counter_record"),
        CheckConstraint("next_inspection_number >= 1", name="ck_safety_counter_inspection"),
        CheckConstraint("next_punch_number >= 1", name="ck_safety_counter_punch"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    next_record_number: Mapped[int] = mapped_column(BigInteger, default=1)
    next_inspection_number: Mapped[int] = mapped_column(BigInteger, default=1)
    next_punch_number: Mapped[int] = mapped_column(BigInteger, default=1)


class SafetyRecord(UUIDTimestampMixin, Base):
    __tablename__ = "safety_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_safety_records_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "reported_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_safety_records_reporter_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_safety_records_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_safety_records_project_number"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_safety_records_id_project_org"
        ),
        CheckConstraint("number >= 1", name="ck_safety_records_number"),
        CheckConstraint("revision >= 1", name="ck_safety_records_revision"),
        Index("ix_safety_records_project_status", "project_id", "status", "number"),
        Index("ix_safety_records_project_type", "project_id", "record_type", "number"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[int] = mapped_column(BigInteger)
    record_type: Mapped[SafetyRecordType] = mapped_column(
        Enum(SafetyRecordType, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[SafetyRecordStatus] = mapped_column(
        Enum(SafetyRecordStatus, native_enum=False, values_callable=enum_values),
        default=SafetyRecordStatus.OPEN,
    )
    severity: Mapped[SafetySeverity] = mapped_column(
        Enum(SafetySeverity, native_enum=False, values_callable=enum_values),
        default=SafetySeverity.MEDIUM,
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reported_by_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SafetyCorrectiveAction(UUIDTimestampMixin, Base):
    __tablename__ = "safety_corrective_actions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["safety_record_id", "project_id", "organization_id"],
            ["safety_records.id", "safety_records.project_id", "safety_records.organization_id"],
            name="fk_safety_actions_record_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "assigned_to_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_safety_actions_assignee_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "safety_record_id", "sequence", name="uq_safety_actions_record_sequence"
        ),
        CheckConstraint("sequence >= 1", name="ck_safety_actions_sequence"),
        CheckConstraint("revision >= 1", name="ck_safety_actions_revision"),
        Index("ix_safety_actions_project_status", "project_id", "status", "due_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    safety_record_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    assigned_to_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[CorrectiveActionStatus] = mapped_column(
        Enum(CorrectiveActionStatus, native_enum=False, values_callable=enum_values),
        default=CorrectiveActionStatus.OPEN,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InspectionTemplate(UUIDTimestampMixin, Base):
    __tablename__ = "inspection_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_inspection_templates_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "key", name="uq_inspection_templates_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_inspection_templates_id_org"),
        CheckConstraint("revision >= 1", name="ck_inspection_templates_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class InspectionTemplateVersion(UUIDTimestampMixin, Base):
    __tablename__ = "inspection_template_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["inspection_templates.id", "inspection_templates.organization_id"],
            name="fk_inspection_versions_template_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "template_id", "version", name="uq_inspection_versions_template_version"
        ),
        UniqueConstraint("id", "organization_id", name="uq_inspection_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_inspection_versions_version"),
        CheckConstraint("revision >= 1", name="ck_inspection_versions_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    template_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[InspectionTemplateVersionStatus] = mapped_column(
        Enum(InspectionTemplateVersionStatus, native_enum=False, values_callable=enum_values),
        default=InspectionTemplateVersionStatus.DRAFT,
    )
    checklist: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InspectionRun(UUIDTimestampMixin, Base):
    __tablename__ = "inspection_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_inspection_runs_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["template_version_id", "organization_id"],
            ["inspection_template_versions.id", "inspection_template_versions.organization_id"],
            name="fk_inspection_runs_template_version_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "inspector_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_inspection_runs_inspector_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_inspection_runs_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_inspection_runs_project_number"),
        UniqueConstraint("id", "organization_id", name="uq_inspection_runs_id_org"),
        CheckConstraint("number >= 1", name="ck_inspection_runs_number"),
        CheckConstraint("revision >= 1", name="ck_inspection_runs_revision"),
        Index("ix_inspection_runs_project_status", "project_id", "status", "number"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[int] = mapped_column(BigInteger)
    template_version_id: Mapped[UUID] = mapped_column(Uuid)
    inspector_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[InspectionRunStatus] = mapped_column(
        Enum(InspectionRunStatus, native_enum=False, values_callable=enum_values),
        default=InspectionRunStatus.DRAFT,
    )
    title: Mapped[str] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InspectionResult(UUIDTimestampMixin, Base):
    __tablename__ = "inspection_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["inspection_run_id", "organization_id"],
            ["inspection_runs.id", "inspection_runs.organization_id"],
            name="fk_inspection_results_run_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("inspection_run_id", "item_key", name="uq_inspection_results_run_item"),
        CheckConstraint("revision >= 1", name="ck_inspection_results_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    inspection_run_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    item_key: Mapped[str] = mapped_column(String(160))
    result: Mapped[InspectionResultStatus] = mapped_column(
        Enum(InspectionResultStatus, native_enum=False, values_callable=enum_values),
        default=InspectionResultStatus.NOT_CHECKED,
    )
    value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class PunchItem(UUIDTimestampMixin, Base):
    __tablename__ = "punch_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_punch_items_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "assigned_to_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_punch_items_assignee_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_punch_items_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_punch_items_project_number"),
        UniqueConstraint("id", "organization_id", name="uq_punch_items_id_org"),
        CheckConstraint("number >= 1", name="ck_punch_items_number"),
        CheckConstraint("revision >= 1", name="ck_punch_items_revision"),
        Index("ix_punch_items_project_status", "project_id", "status", "number"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[PunchPriority] = mapped_column(
        Enum(PunchPriority, native_enum=False, values_callable=enum_values),
        default=PunchPriority.MEDIUM,
    )
    status: Mapped[PunchItemStatus] = mapped_column(
        Enum(PunchItemStatus, native_enum=False, values_callable=enum_values),
        default=PunchItemStatus.OPEN,
    )
    assigned_to_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
