"""Add India scheduling foundation.

Revision ID: 20260910_0040
Revises: 20260910_0039
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0040"
down_revision: str | None = "20260910_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("scheduling.module.view", "module", "view", "Access project scheduling.", "medium"),
    ("scheduling.schedule.view", "schedule", "view", "View project schedules, activities, baselines and progress.", "medium"),
    ("scheduling.schedule.manage", "schedule", "manage", "Create and revise schedules, activities and dependencies.", "high"),
    ("scheduling.baseline.create", "baseline", "create", "Create an immutable schedule baseline.", "critical"),
    ("scheduling.progress.update", "progress", "update", "Record project schedule progress.", "high"),
    ("scheduling.schedule.complete", "schedule", "complete", "Complete an active schedule after all activities finish.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "project_schedules",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("draft", "active", "completed", "archived", name="schedulestatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("active_baseline_version", sa.Integer(), nullable=True),
        sa.Column("data_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_schedules_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_project_schedules_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_project_schedules"),
        sa.UniqueConstraint("project_id", "code", name="uq_project_schedules_project_code"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_project_schedules_scope"),
    )
    op.create_index("ix_project_schedules_project_status", "project_schedules", ["project_id", "status"])

    op.create_table(
        "schedule_activities",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("activity_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("responsible_membership_id", sa.Uuid(), nullable=True),
        sa.Column("planned_start", sa.Date(), nullable=False),
        sa.Column("planned_finish", sa.Date(), nullable=False),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_finish", sa.Date(), nullable=True),
        sa.Column("percent_complete", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("not_started", "in_progress", "completed", "on_hold", name="activitystatus", native_enum=False), nullable=False, server_default="not_started"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("planned_finish >= planned_start", name="ck_schedule_activity_planned_dates"),
        sa.CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_schedule_activity_percent"),
        sa.CheckConstraint("revision >= 1", name="ck_schedule_activity_revision"),
        sa.ForeignKeyConstraint(["schedule_id", "project_id", "organization_id"], ["project_schedules.id", "project_schedules.project_id", "project_schedules.organization_id"], name="fk_schedule_activities_schedule_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_schedule_activities_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "responsible_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_schedule_activities_responsible_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_activities"),
        sa.UniqueConstraint("schedule_id", "activity_code", name="uq_schedule_activity_code"),
        sa.UniqueConstraint("id", "schedule_id", "project_id", "organization_id", name="uq_schedule_activity_scope"),
    )
    op.create_index("ix_schedule_activities_project_status", "schedule_activities", ["project_id", "status"])
    op.create_index("ix_schedule_activities_schedule_dates", "schedule_activities", ["schedule_id", "planned_start", "planned_finish"])

    op.create_table(
        "schedule_dependencies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_activity_id", sa.Uuid(), nullable=False),
        sa.Column("successor_activity_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_type", sa.Enum("finish_start", "start_start", "finish_finish", "start_finish", name="dependencytype", native_enum=False), nullable=False, server_default="finish_start"),
        sa.Column("lag_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("predecessor_activity_id <> successor_activity_id", name="ck_schedule_dependency_not_self"),
        sa.ForeignKeyConstraint(["predecessor_activity_id", "schedule_id", "project_id", "organization_id"], ["schedule_activities.id", "schedule_activities.schedule_id", "schedule_activities.project_id", "schedule_activities.organization_id"], name="fk_schedule_dependencies_predecessor_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["successor_activity_id", "schedule_id", "project_id", "organization_id"], ["schedule_activities.id", "schedule_activities.schedule_id", "schedule_activities.project_id", "schedule_activities.organization_id"], name="fk_schedule_dependencies_successor_scope", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_dependencies"),
        sa.UniqueConstraint("predecessor_activity_id", "successor_activity_id", "dependency_type", name="uq_schedule_dependency_pair"),
    )
    op.create_index("ix_schedule_dependencies_schedule", "schedule_dependencies", ["schedule_id"])

    op.create_table(
        "schedule_baselines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version_number >= 1", name="ck_schedule_baseline_version"),
        sa.ForeignKeyConstraint(["schedule_id", "project_id", "organization_id"], ["project_schedules.id", "project_schedules.project_id", "project_schedules.organization_id"], name="fk_schedule_baselines_schedule_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "created_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_schedule_baselines_creator_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_baselines"),
        sa.UniqueConstraint("schedule_id", "version_number", name="uq_schedule_baseline_version"),
    )
    op.create_index("ix_schedule_baselines_schedule_version", "schedule_baselines", ["schedule_id", "version_number"])

    op.create_table(
        "schedule_progress_updates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("percent_complete", sa.Numeric(6, 2), nullable=False),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_finish", sa.Date(), nullable=True),
        sa.Column("recorded_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_schedule_progress_percent"),
        sa.ForeignKeyConstraint(["activity_id", "schedule_id", "project_id", "organization_id"], ["schedule_activities.id", "schedule_activities.schedule_id", "schedule_activities.project_id", "schedule_activities.organization_id"], name="fk_schedule_progress_activity_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "recorded_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_schedule_progress_recorder_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_progress_updates"),
    )
    op.create_index("ix_schedule_progress_activity_date", "schedule_progress_updates", ["activity_id", "data_date"])

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String),
        sa.column("module", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.Text),
        sa.column("risk", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": "scheduling",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys))
    op.drop_table("schedule_progress_updates")
    op.drop_table("schedule_baselines")
    op.drop_table("schedule_dependencies")
    op.drop_table("schedule_activities")
    op.drop_table("project_schedules")
