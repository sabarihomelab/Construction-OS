"""Create durable background jobs foundation.

Revision ID: 20260910_0009
Revises: 20260910_0008
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0009"
down_revision: str | None = "20260910_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_PERMISSIONS = (
    (
        "admin.operations.jobs.view",
        "admin",
        "operations_jobs",
        "view",
        "View tenant-scoped background job status and failure diagnostics.",
        "high",
    ),
    (
        "admin.operations.jobs.manage",
        "admin",
        "operations_jobs",
        "manage",
        "Retry, cancel, or otherwise manage tenant-scoped background jobs.",
        "critical",
    ),
)


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("risk", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": module,
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, module, resource, action, description, risk in _JOB_PERMISSIONS
        ],
    )

    op.create_table(
        "background_jobs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=160), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "retrying",
                "succeeded",
                "failed",
                "cancelled",
                name="jobstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(length=255), nullable=True),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("schema_version >= 1", name="ck_background_jobs_schema_version"),
        sa.CheckConstraint("priority BETWEEN -100 AND 100", name="ck_background_jobs_priority"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_background_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_background_jobs_max_attempts"),
        sa.CheckConstraint("attempt_count <= max_attempts", name="ck_background_jobs_attempt_count_max"),
        sa.CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_background_jobs_progress_percent"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_background_jobs_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_background_jobs_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_jobs")),
        sa.UniqueConstraint("id", "organization_id", name="uq_background_jobs_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "job_type",
            "idempotency_key",
            name="uq_background_jobs_org_type_idempotency",
        ),
    )
    op.create_index(op.f("ix_background_jobs_organization_id"), "background_jobs", ["organization_id"])
    op.create_index(op.f("ix_background_jobs_job_type"), "background_jobs", ["job_type"])
    op.create_index(op.f("ix_background_jobs_status"), "background_jobs", ["status"])
    op.create_index(op.f("ix_background_jobs_available_at"), "background_jobs", ["available_at"])
    op.create_index(op.f("ix_background_jobs_correlation_id"), "background_jobs", ["correlation_id"])
    op.create_index(
        "ix_background_jobs_queue",
        "background_jobs",
        ["status", "available_at", "priority", "created_at"],
    )
    op.create_index(
        "ix_background_jobs_org_status",
        "background_jobs",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_background_jobs_org_type",
        "background_jobs",
        ["organization_id", "job_type"],
    )
    op.create_index(
        "ix_background_jobs_lease",
        "background_jobs",
        ["status", "lease_expires_at"],
    )

    op.create_table(
        "background_job_attempts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "failed",
                "abandoned",
                "cancelled",
                name="jobattemptstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="running",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("processed_items", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("attempt_number >= 1", name="ck_background_job_attempt_number"),
        sa.CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="ck_background_job_attempt_progress_percent",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["background_jobs.id", "background_jobs.organization_id"],
            name="fk_background_job_attempts_job_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_job_attempts")),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_background_job_attempt_number"),
    )
    op.create_index(op.f("ix_background_job_attempts_organization_id"), "background_job_attempts", ["organization_id"])
    op.create_index(op.f("ix_background_job_attempts_job_id"), "background_job_attempts", ["job_id"])
    op.create_index(op.f("ix_background_job_attempts_worker_id"), "background_job_attempts", ["worker_id"])
    op.create_index(
        "ix_background_job_attempts_org_job",
        "background_job_attempts",
        ["organization_id", "job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_background_job_attempts_org_job", table_name="background_job_attempts")
    op.drop_index(op.f("ix_background_job_attempts_worker_id"), table_name="background_job_attempts")
    op.drop_index(op.f("ix_background_job_attempts_job_id"), table_name="background_job_attempts")
    op.drop_index(op.f("ix_background_job_attempts_organization_id"), table_name="background_job_attempts")
    op.drop_table("background_job_attempts")

    op.drop_index("ix_background_jobs_lease", table_name="background_jobs")
    op.drop_index("ix_background_jobs_org_type", table_name="background_jobs")
    op.drop_index("ix_background_jobs_org_status", table_name="background_jobs")
    op.drop_index("ix_background_jobs_queue", table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_correlation_id"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_available_at"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_status"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_job_type"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_organization_id"), table_name="background_jobs")
    op.drop_table("background_jobs")

    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(
        permissions.delete().where(
            permissions.c.key.in_([permission[0] for permission in _JOB_PERMISSIONS])
        )
    )
