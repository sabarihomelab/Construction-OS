from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
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


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class BackgroundJob(UUIDTimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_background_jobs_id_org"),
        UniqueConstraint(
            "organization_id",
            "job_type",
            "idempotency_key",
            name="uq_background_jobs_org_type_idempotency",
        ),
        CheckConstraint("schema_version >= 1", name="ck_background_jobs_schema_version"),
        CheckConstraint("priority BETWEEN -100 AND 100", name="ck_background_jobs_priority"),
        CheckConstraint("attempt_count >= 0", name="ck_background_jobs_attempt_count"),
        CheckConstraint("max_attempts >= 1", name="ck_background_jobs_max_attempts"),
        CheckConstraint(
            "attempt_count <= max_attempts",
            name="ck_background_jobs_attempt_count_max",
        ),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="ck_background_jobs_progress_percent",
        ),
        Index(
            "ix_background_jobs_queue",
            "status",
            "available_at",
            "priority",
            "created_at",
        ),
        Index("ix_background_jobs_org_status", "organization_id", "status"),
        Index("ix_background_jobs_org_type", "organization_id", "job_type"),
        Index("ix_background_jobs_lease", "status", "lease_expires_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(160), index=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, values_callable=enum_values),
        default=JobStatus.QUEUED,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    correlation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)


class BackgroundJobAttempt(UUIDTimestampMixin, Base):
    __tablename__ = "background_job_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["background_jobs.id", "background_jobs.organization_id"],
            name="fk_background_job_attempts_job_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_id", "attempt_number", name="uq_background_job_attempt_number"),
        CheckConstraint("attempt_number >= 1", name="ck_background_job_attempt_number"),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="ck_background_job_attempt_progress_percent",
        ),
        Index("ix_background_job_attempts_org_job", "organization_id", "job_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    job_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[JobAttemptStatus] = mapped_column(
        Enum(JobAttemptStatus, native_enum=False, values_callable=enum_values),
        default=JobAttemptStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    processed_items: Mapped[int] = mapped_column(BigInteger, default=0)
