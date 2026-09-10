"""Add Workforce and Time foundation.

Revision ID: 20260910_0031
Revises: 20260910_0030
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0031"
down_revision: str | None = "20260910_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WORKFORCE_PERMISSIONS = (
    ("workforce.worker.view", "worker", "view", "View the company worker directory and permitted workforce details.", "medium"),
    ("workforce.worker.manage", "worker", "manage", "Create, update, link, deactivate and terminate Worker records.", "high"),
    ("workforce.crew.view", "crew", "view", "View company crews and crew membership.", "medium"),
    ("workforce.crew.manage", "crew", "manage", "Create and manage crews and crew membership history.", "high"),
    ("workforce.assignment.view", "assignment", "view", "View worker assignments within the authorized project scope.", "medium"),
    ("workforce.assignment.manage", "assignment", "manage", "Assign, suspend and end workers within the authorized project scope.", "high"),
    ("workforce.timecard.view", "timecard", "view", "View timecards and time entries within the authorized project scope.", "medium"),
    ("workforce.timecard.create", "timecard", "create", "Create project timecards for actively assigned workers.", "medium"),
    ("workforce.timecard.update", "timecard", "update", "Edit draft or rejected timecard entries.", "medium"),
    ("workforce.timecard.submit", "timecard", "submit", "Submit timecards under effective project rules and workflow configuration.", "high"),
    ("workforce.timecard.approve", "timecard", "approve", "Approve or reject timecards through the shared Workflow engine.", "high"),
    ("workforce.timecard.manage", "timecard", "manage", "Perform controlled timecard administration and correction actions.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("worker_number", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=False),
        sa.Column("preferred_name", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("job_title", sa.String(length=160), nullable=True),
        sa.Column("trade", sa.String(length=120), nullable=True),
        sa.Column("classification", sa.String(length=120), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "terminated", name="employmentstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("organization_membership_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_workers_revision"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_workers_organization", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_workers_org_membership_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workers"),
        sa.UniqueConstraint("organization_id", "worker_number", name="uq_workers_org_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_workers_id_org"),
        sa.UniqueConstraint(
            "organization_id", "organization_membership_id", name="uq_workers_org_membership"
        ),
    )
    op.create_index("ix_workers_organization_id", "workers", ["organization_id"])
    op.create_index("ix_workers_worker_number", "workers", ["worker_number"])
    op.create_index("ix_workers_org_status", "workers", ["organization_id", "status"])
    op.create_index("ix_workers_org_name", "workers", ["organization_id", "last_name", "first_name"])

    op.create_table(
        "crews",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("supervisor_worker_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="crewstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_crews_revision"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_crews_organization", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supervisor_worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_crews_supervisor_worker_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crews"),
        sa.UniqueConstraint("organization_id", "name", name="uq_crews_org_name"),
        sa.UniqueConstraint("id", "organization_id", name="uq_crews_id_org"),
    )
    op.create_index("ix_crews_organization_id", "crews", ["organization_id"])
    op.create_index("ix_crews_name", "crews", ["name"])
    op.create_index("ix_crews_org_status", "crews", ["organization_id", "status"])

    op.create_table(
        "crew_memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("crew_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_crew_memberships_date_range",
        ),
        sa.ForeignKeyConstraint(
            ["crew_id", "organization_id"],
            ["crews.id", "crews.organization_id"],
            name="fk_crew_memberships_crew_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_crew_memberships_worker_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crew_memberships"),
        sa.UniqueConstraint(
            "crew_id", "worker_id", "effective_from", name="uq_crew_memberships_crew_worker_start"
        ),
    )
    op.create_index("ix_crew_memberships_organization_id", "crew_memberships", ["organization_id"])
    op.create_index("ix_crew_memberships_crew_id", "crew_memberships", ["crew_id"])
    op.create_index("ix_crew_memberships_worker_id", "crew_memberships", ["worker_id"])
    op.create_index("ix_crew_memberships_worker", "crew_memberships", ["organization_id", "worker_id"])
    op.create_index("ix_crew_memberships_crew", "crew_memberships", ["organization_id", "crew_id"])

    op.create_table(
        "project_worker_assignments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("crew_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", "ended", name="projectworkerassignmentstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("project_role", sa.String(length=160), nullable=True),
        sa.Column("trade", sa.String(length=120), nullable=True),
        sa.Column("default_cost_code", sa.String(length=80), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_worker_assignments_revision"),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_project_worker_assignments_date_range",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_worker_assignments_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_project_worker_assignments_worker_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["crew_id", "organization_id"],
            ["crews.id", "crews.organization_id"],
            name="fk_project_worker_assignments_crew_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_worker_assignments"),
        sa.UniqueConstraint(
            "project_id", "worker_id", name="uq_project_worker_assignments_project_worker"
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_project_worker_assignments_id_org"),
    )
    op.create_index("ix_project_worker_assignments_organization_id", "project_worker_assignments", ["organization_id"])
    op.create_index("ix_project_worker_assignments_project_id", "project_worker_assignments", ["project_id"])
    op.create_index("ix_project_worker_assignments_worker_id", "project_worker_assignments", ["worker_id"])
    op.create_index(
        "ix_project_worker_assignments_project_status",
        "project_worker_assignments",
        ["project_id", "status"],
    )

    op.create_table(
        "timecards",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "in_review",
                "approved",
                "rejected",
                "void",
                name="timecardstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
        sa.Column(
            "configuration_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_timecards_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_timecards_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_timecards_worker_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_timecards_workflow_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_timecards_creator", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_timecards"),
        sa.UniqueConstraint(
            "project_id", "worker_id", "week_start", name="uq_timecards_project_worker_week"
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_timecards_id_org"),
    )
    op.create_index("ix_timecards_organization_id", "timecards", ["organization_id"])
    op.create_index("ix_timecards_project_id", "timecards", ["project_id"])
    op.create_index("ix_timecards_worker_id", "timecards", ["worker_id"])
    op.create_index("ix_timecards_week_start", "timecards", ["week_start"])
    op.create_index("ix_timecards_project_week", "timecards", ["project_id", "week_start"])
    op.create_index("ix_timecards_project_status", "timecards", ["project_id", "status", "week_start"])

    op.create_table(
        "time_entries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("timecard_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("regular_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("double_time_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("cost_code", sa.String(length=80), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("work_description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(length=160), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("regular_hours >= 0", name="ck_time_entries_regular_hours"),
        sa.CheckConstraint("overtime_hours >= 0", name="ck_time_entries_overtime_hours"),
        sa.CheckConstraint("double_time_hours >= 0", name="ck_time_entries_double_time_hours"),
        sa.CheckConstraint(
            "regular_hours + overtime_hours + double_time_hours <= 24",
            name="ck_time_entries_daily_hours",
        ),
        sa.ForeignKeyConstraint(
            ["timecard_id", "organization_id"],
            ["timecards.id", "timecards.organization_id"],
            name="fk_time_entries_timecard_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_time_entries"),
    )
    op.create_index("ix_time_entries_organization_id", "time_entries", ["organization_id"])
    op.create_index("ix_time_entries_timecard_id", "time_entries", ["timecard_id"])
    op.create_index("ix_time_entries_work_date", "time_entries", ["work_date"])
    op.create_index("ix_time_entries_timecard_date", "time_entries", ["timecard_id", "work_date"])

    op.create_table(
        "timecard_history_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("timecard_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "created",
                "updated",
                "submitted",
                "approved",
                "rejected",
                "reopened",
                "voided",
                name="timecardhistorytype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("timecard_revision", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("timecard_revision >= 1", name="ck_timecard_history_revision"),
        sa.ForeignKeyConstraint(
            ["timecard_id", "organization_id"],
            ["timecards.id", "timecards.organization_id"],
            name="fk_timecard_history_timecard_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_timecard_history_actor", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_timecard_history_events"),
    )
    op.create_index("ix_timecard_history_events_organization_id", "timecard_history_events", ["organization_id"])
    op.create_index("ix_timecard_history_timecard", "timecard_history_events", ["timecard_id", "created_at"])

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
                "module": "workforce",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _WORKFORCE_PERMISSIONS
        ],
    )


def downgrade() -> None:
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(
        permissions.delete().where(
            permissions.c.key.in_([key for key, *_ in _WORKFORCE_PERMISSIONS])
        )
    )
    op.drop_table("timecard_history_events")
    op.drop_table("time_entries")
    op.drop_table("timecards")
    op.drop_table("project_worker_assignments")
    op.drop_table("crew_memberships")
    op.drop_table("crews")
    op.drop_table("workers")
