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


class DataClassification(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DispositionAction(StrEnum):
    ARCHIVE = "archive"
    DELETE = "delete"
    REVIEW = "review"


class PolicyVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class LegalHoldStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class LifecycleRunStatus(StrEnum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    READY = "ready"
    APPLYING = "applying"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class DataLifecyclePolicy(UUIDTimestampMixin, Base):
    __tablename__ = "data_lifecycle_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_data_lifecycle_policies_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_data_lifecycle_policies_id_org"),
        CheckConstraint("current_version >= 0", name="ck_data_lifecycle_policies_current_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(180))
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)


class DataLifecyclePolicyVersion(UUIDTimestampMixin, Base):
    __tablename__ = "data_lifecycle_policy_versions"
    __table_args__ = (
        ForeignKeyConstraint(["policy_id", "organization_id"], ["data_lifecycle_policies.id", "data_lifecycle_policies.organization_id"], name="fk_data_lifecycle_policy_versions_policy_org", ondelete="CASCADE"),
        UniqueConstraint("policy_id", "version", name="uq_data_lifecycle_policy_versions_version"),
        UniqueConstraint("id", "organization_id", name="uq_data_lifecycle_policy_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_data_lifecycle_policy_versions_version"),
        CheckConstraint("retention_days >= 0", name="ck_data_lifecycle_policy_versions_retention_days"),
        Index("ix_data_lifecycle_policy_versions_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    policy_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[PolicyVersionStatus] = mapped_column(Enum(PolicyVersionStatus, native_enum=False, values_callable=enum_values), default=PolicyVersionStatus.DRAFT)
    classification: Mapped[DataClassification] = mapped_column(Enum(DataClassification, native_enum=False, values_callable=enum_values))
    retention_days: Mapped[int] = mapped_column(Integer)
    disposition_action: Mapped[DispositionAction] = mapped_column(Enum(DispositionAction, native_enum=False, values_callable=enum_values))
    conditions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class LegalHold(UUIDTimestampMixin, Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        UniqueConstraint("organization_id", "hold_key", name="uq_legal_holds_org_key"),
        Index("ix_legal_holds_org_scope_status", "organization_id", "scope_type", "scope_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    hold_key: Mapped[str] = mapped_column(String(140))
    scope_type: Mapped[str] = mapped_column(String(80))
    scope_id: Mapped[str] = mapped_column(String(160))
    status: Mapped[LegalHoldStatus] = mapped_column(Enum(LegalHoldStatus, native_enum=False, values_callable=enum_values), default=LegalHoldStatus.ACTIVE)
    reason: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    released_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class LifecycleRun(UUIDTimestampMixin, Base):
    __tablename__ = "lifecycle_runs"
    __table_args__ = (
        ForeignKeyConstraint(["policy_version_id", "organization_id"], ["data_lifecycle_policy_versions.id", "data_lifecycle_policy_versions.organization_id"], name="fk_lifecycle_runs_policy_version_org", ondelete="RESTRICT"),
        CheckConstraint("candidate_count >= 0", name="ck_lifecycle_runs_candidate_count"),
        CheckConstraint("blocked_count >= 0", name="ck_lifecycle_runs_blocked_count"),
        CheckConstraint("applied_count >= 0", name="ck_lifecycle_runs_applied_count"),
        Index("ix_lifecycle_runs_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    policy_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    scope_type: Mapped[str] = mapped_column(String(80))
    scope_id: Mapped[str] = mapped_column(String(160))
    status: Mapped[LifecycleRunStatus] = mapped_column(Enum(LifecycleRunStatus, native_enum=False, values_callable=enum_values), default=LifecycleRunStatus.DRAFT)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    applied_count: Mapped[int] = mapped_column(Integer, default=0)
    analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    initiated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
