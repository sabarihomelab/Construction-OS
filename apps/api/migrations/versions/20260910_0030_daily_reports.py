"""Add configurable project Daily Reports.

Revision ID: 20260910_0030
Revises: 20260910_0029
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0030"
down_revision: str | None = "20260910_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIELD_PERMISSIONS = (
    ("field.daily_report.view", "view", "View Daily Reports within the authorized project scope.", "medium"),
    ("field.daily_report.create", "create", "Create Daily Report drafts within the authorized project scope.", "medium"),
    ("field.daily_report.update", "update", "Update Daily Report drafts and configured sections.", "medium"),
    ("field.daily_report.submit", "submit", "Submit Daily Reports using effective project configuration.", "high"),
    ("field.daily_report.approve", "approve", "Approve or reject Daily Reports requiring review.", "high"),
    ("field.daily_report.manage", "manage", "Perform controlled Daily Report administrative actions.", "high"),
)


def _id_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def _child_table(name: str, *columns: sa.Column, checks: tuple[sa.CheckConstraint, ...] = ()) -> None:
    op.create_table(
        name,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("daily_report_id", sa.Uuid(), nullable=False),
        *columns,
        *_id_timestamps(),
        *checks,
        sa.ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name=f"fk_{name}_report_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{name}"),
    )
    op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])
    op.create_index(f"ix_{name}_daily_report_id", name, ["daily_report_id"])


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("shift_code", sa.String(length=40), nullable=False, server_default="day"),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "in_review",
                "approved",
                "rejected",
                "void",
                name="dailyreportstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("prepared_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("weather_condition", sa.String(length=120), nullable=True),
        sa.Column("temperature_low", sa.Numeric(8, 2), nullable=True),
        sa.Column("temperature_high", sa.Numeric(8, 2), nullable=True),
        sa.Column("temperature_unit", sa.String(length=12), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        *_id_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_daily_reports_revision"),
        sa.CheckConstraint(
            "temperature_low IS NULL OR temperature_high IS NULL OR temperature_low <= temperature_high",
            name="ck_daily_reports_temperature_range",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_daily_reports_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "prepared_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_daily_reports_preparer_project_member_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_daily_reports_workflow_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_daily_reports_creator",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_reports"),
        sa.UniqueConstraint("id", "organization_id", name="uq_daily_reports_id_org"),
        sa.UniqueConstraint(
            "project_id", "report_date", "shift_code", name="uq_daily_reports_project_date_shift"
        ),
    )
    op.create_index("ix_daily_reports_organization_id", "daily_reports", ["organization_id"])
    op.create_index("ix_daily_reports_project_id", "daily_reports", ["project_id"])
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"])
    op.create_index("ix_daily_reports_prepared_by", "daily_reports", ["prepared_by_membership_id"])
    op.create_index("ix_daily_reports_project_date", "daily_reports", ["project_id", "report_date"])
    op.create_index(
        "ix_daily_reports_project_status", "daily_reports", ["project_id", "status", "report_date"]
    )

    _child_table(
        "daily_report_crew_entries",
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("trade", sa.String(length=120), nullable=True),
        sa.Column("worker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("regular_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        checks=(
            sa.CheckConstraint("worker_count >= 0", name="ck_daily_report_crew_worker_count"),
            sa.CheckConstraint("regular_hours >= 0", name="ck_daily_report_crew_regular_hours"),
            sa.CheckConstraint("overtime_hours >= 0", name="ck_daily_report_crew_overtime_hours"),
        ),
    )
    _child_table(
        "daily_report_work_entries",
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("cost_code", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_code", sa.String(length=24), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        checks=(sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_daily_report_work_quantity"),),
    )
    _child_table(
        "daily_report_equipment_entries",
        sa.Column("equipment_name", sa.String(length=255), nullable=False),
        sa.Column("equipment_reference", sa.String(length=160), nullable=True),
        sa.Column("hours_operated", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        checks=(sa.CheckConstraint("hours_operated >= 0", name="ck_daily_report_equipment_hours"),),
    )
    _child_table(
        "daily_report_delivery_entries",
        sa.Column("supplier", sa.String(length=255), nullable=True),
        sa.Column("material", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_code", sa.String(length=24), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticket_number", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        checks=(sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_daily_report_delivery_quantity"),),
    )
    _child_table(
        "daily_report_production_entries",
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("cost_code", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_code", sa.String(length=24), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        checks=(sa.CheckConstraint("quantity >= 0", name="ck_daily_report_production_quantity"),),
    )
    _child_table(
        "daily_report_delay_entries",
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("responsible_party", sa.String(length=255), nullable=True),
        sa.Column("schedule_impact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        checks=(
            sa.CheckConstraint("lost_hours IS NULL OR lost_hours >= 0", name="ck_daily_report_delay_hours"),
            sa.CheckConstraint(
                "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
                name="ck_daily_report_delay_time_range",
            ),
        ),
    )
    _child_table(
        "daily_report_safety_entries",
        sa.Column("entry_type", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=True),
        sa.Column("safety_record_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "daily_report_history_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("daily_report_id", sa.Uuid(), nullable=False),
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
                name="dailyreporthistorytype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("report_revision", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *_id_timestamps(),
        sa.CheckConstraint("report_revision >= 1", name="ck_daily_report_history_revision"),
        sa.ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_history_report_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_daily_report_history_actor", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_report_history_events"),
    )
    op.create_index("ix_daily_report_history_org", "daily_report_history_events", ["organization_id"])
    op.create_index("ix_daily_report_history_report", "daily_report_history_events", ["daily_report_id", "created_at"])

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
                "module": "field",
                "resource": "daily_report",
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, action, description, risk in _FIELD_PERMISSIONS
        ],
    )

    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_key) "
            "SELECT role_id, 'field.daily_report.view' FROM role_permissions "
            "WHERE permission_key = 'field.daily_log.view' "
            "ON CONFLICT DO NOTHING"
        )
    )
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_key = 'field.daily_log.view'"))
    op.execute(sa.text("DELETE FROM permissions WHERE key = 'field.daily_log.view'"))


def downgrade() -> None:
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    keys = [key for key, *_ in _FIELD_PERMISSIONS]
    op.execute(permissions.delete().where(permissions.c.key.in_(keys)))
    op.drop_table("daily_report_history_events")
    op.drop_table("daily_report_safety_entries")
    op.drop_table("daily_report_delay_entries")
    op.drop_table("daily_report_production_entries")
    op.drop_table("daily_report_delivery_entries")
    op.drop_table("daily_report_equipment_entries")
    op.drop_table("daily_report_work_entries")
    op.drop_table("daily_report_crew_entries")
    op.drop_table("daily_reports")
