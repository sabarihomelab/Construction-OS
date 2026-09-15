"""Add Safety, Inspections, and Punch foundation.

Revision ID: 20260910_0032
Revises: 20260910_0031
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0032"
down_revision: str | None = "20260910_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("safety.module.view", "module", "view", "Access Safety, Inspections, and Punch within authorized projects.", "medium"),
    ("safety.record.view", "record", "view", "View permitted safety records and corrective actions.", "high"),
    ("safety.record.create", "record", "create", "Create project safety records.", "high"),
    ("safety.record.update", "record", "update", "Update open safety records and corrective actions.", "high"),
    ("safety.record.close", "record", "close", "Close resolved safety records.", "high"),
    ("safety.record.manage", "record", "manage", "Perform controlled safety-record administration.", "critical"),
    ("safety.inspection.view", "inspection", "view", "View inspection templates and project inspection runs.", "medium"),
    ("safety.inspection.create", "inspection", "create", "Create project inspection runs.", "medium"),
    ("safety.inspection.execute", "inspection", "execute", "Record and submit inspection results.", "high"),
    ("safety.inspection.review", "inspection", "review", "Approve or reject inspections through shared Workflow.", "high"),
    ("safety.inspection.manage", "inspection", "manage", "Create, publish, and retire inspection templates.", "high"),
    ("safety.punch.view", "punch", "view", "View Punch items within the authorized project.", "medium"),
    ("safety.punch.create", "punch", "create", "Create Punch items within the authorized project.", "medium"),
    ("safety.punch.update", "punch", "update", "Update open Punch items.", "medium"),
    ("safety.punch.close", "punch", "close", "Close completed Punch items.", "high"),
    ("safety.punch.manage", "punch", "manage", "Perform controlled Punch administration.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "safety_project_counters",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("next_record_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("next_inspection_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("next_punch_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("next_record_number >= 1", name="ck_safety_counter_record"),
        sa.CheckConstraint("next_inspection_number >= 1", name="ck_safety_counter_inspection"),
        sa.CheckConstraint("next_punch_number >= 1", name="ck_safety_counter_punch"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_safety_counter_project_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organization_id", "project_id", name="pk_safety_project_counters"),
    )

    op.create_table(
        "safety_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column(
            "record_type",
            sa.Enum("hazard", "observation", "incident", "near_miss", "toolbox_talk", name="safetyrecordtype", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "in_review", "closed", "void", name="safetyrecordstatus", native_enum=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="safetyseverity", native_enum=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reported_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("number >= 1", name="ck_safety_records_number"),
        sa.CheckConstraint("revision >= 1", name="ck_safety_records_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_safety_records_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "reported_by_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_safety_records_reporter_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_safety_records_workflow_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_safety_records"),
        sa.UniqueConstraint("project_id", "number", name="uq_safety_records_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_safety_records_id_project_org"),
    )
    op.create_index("ix_safety_records_organization_id", "safety_records", ["organization_id"])
    op.create_index("ix_safety_records_project_id", "safety_records", ["project_id"])
    op.create_index("ix_safety_records_reported_by", "safety_records", ["reported_by_membership_id"])
    op.create_index("ix_safety_records_project_status", "safety_records", ["project_id", "status", "number"])
    op.create_index("ix_safety_records_project_type", "safety_records", ["project_id", "record_type", "number"])

    op.create_table(
        "safety_corrective_actions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("safety_record_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assigned_to_membership_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "completed", "cancelled", name="correctiveactionstatus", native_enum=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_safety_actions_sequence"),
        sa.CheckConstraint("revision >= 1", name="ck_safety_actions_revision"),
        sa.ForeignKeyConstraint(
            ["safety_record_id", "project_id", "organization_id"],
            ["safety_records.id", "safety_records.project_id", "safety_records.organization_id"],
            name="fk_safety_actions_record_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "assigned_to_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_safety_actions_assignee_project_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_safety_corrective_actions"),
        sa.UniqueConstraint("safety_record_id", "sequence", name="uq_safety_actions_record_sequence"),
    )
    op.create_index("ix_safety_actions_org", "safety_corrective_actions", ["organization_id"])
    op.create_index("ix_safety_actions_record", "safety_corrective_actions", ["safety_record_id"])
    op.create_index("ix_safety_actions_project_status", "safety_corrective_actions", ["project_id", "status", "due_date"])

    op.create_table(
        "inspection_templates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_inspection_templates_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_inspection_templates_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_inspection_templates"),
        sa.UniqueConstraint("organization_id", "key", name="uq_inspection_templates_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inspection_templates_id_org"),
    )
    op.create_index("ix_inspection_templates_org", "inspection_templates", ["organization_id"])
    op.create_index("ix_inspection_templates_key", "inspection_templates", ["key"])

    op.create_table(
        "inspection_template_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "retired", name="inspectiontemplateversionstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("checklist", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_inspection_versions_version"),
        sa.CheckConstraint("revision >= 1", name="ck_inspection_versions_revision"),
        sa.ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["inspection_templates.id", "inspection_templates.organization_id"],
            name="fk_inspection_versions_template_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inspection_template_versions"),
        sa.UniqueConstraint("template_id", "version", name="uq_inspection_versions_template_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inspection_versions_id_org"),
    )
    op.create_index("ix_inspection_versions_org", "inspection_template_versions", ["organization_id"])
    op.create_index("ix_inspection_versions_template", "inspection_template_versions", ["template_id"])

    op.create_table(
        "inspection_runs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("template_version_id", sa.Uuid(), nullable=False),
        sa.Column("inspector_membership_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "in_progress", "submitted", "in_review", "approved", "rejected", "void", name="inspectionrunstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("number >= 1", name="ck_inspection_runs_number"),
        sa.CheckConstraint("revision >= 1", name="ck_inspection_runs_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_inspection_runs_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_version_id", "organization_id"], ["inspection_template_versions.id", "inspection_template_versions.organization_id"], name="fk_inspection_runs_template_version_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id", "inspector_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_inspection_runs_inspector_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workflow_instance_id", "organization_id"], ["workflow_instances.id", "workflow_instances.organization_id"], name="fk_inspection_runs_workflow_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_inspection_runs"),
        sa.UniqueConstraint("project_id", "number", name="uq_inspection_runs_project_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inspection_runs_id_org"),
    )
    op.create_index("ix_inspection_runs_org", "inspection_runs", ["organization_id"])
    op.create_index("ix_inspection_runs_project", "inspection_runs", ["project_id"])
    op.create_index("ix_inspection_runs_project_status", "inspection_runs", ["project_id", "status", "number"])

    op.create_table(
        "inspection_results",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_run_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column(
            "result",
            sa.Enum("not_checked", "pass", "fail", "not_applicable", name="inspectionresultstatus", native_enum=False),
            nullable=False,
            server_default="not_checked",
        ),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_inspection_results_revision"),
        sa.ForeignKeyConstraint(["inspection_run_id", "organization_id"], ["inspection_runs.id", "inspection_runs.organization_id"], name="fk_inspection_results_run_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_inspection_results"),
        sa.UniqueConstraint("inspection_run_id", "item_key", name="uq_inspection_results_run_item"),
    )
    op.create_index("ix_inspection_results_org", "inspection_results", ["organization_id"])
    op.create_index("ix_inspection_results_run", "inspection_results", ["inspection_run_id"])

    op.create_table(
        "punch_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "critical", name="punchpriority", native_enum=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "ready_for_review", "closed", "void", name="punchitemstatus", native_enum=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("assigned_to_membership_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_id", sa.String(length=160), nullable=True),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("number >= 1", name="ck_punch_items_number"),
        sa.CheckConstraint("revision >= 1", name="ck_punch_items_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_punch_items_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "assigned_to_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_punch_items_assignee_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workflow_instance_id", "organization_id"], ["workflow_instances.id", "workflow_instances.organization_id"], name="fk_punch_items_workflow_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_punch_items"),
        sa.UniqueConstraint("project_id", "number", name="uq_punch_items_project_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_punch_items_id_org"),
    )
    op.create_index("ix_punch_items_org", "punch_items", ["organization_id"])
    op.create_index("ix_punch_items_project", "punch_items", ["project_id"])
    op.create_index("ix_punch_items_project_status", "punch_items", ["project_id", "status", "number"])

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
                "module": "safety",
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
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(permissions.delete().where(permissions.c.key.in_([key for key, *_ in _PERMISSIONS])))
    op.drop_table("punch_items")
    op.drop_table("inspection_results")
    op.drop_table("inspection_runs")
    op.drop_table("inspection_template_versions")
    op.drop_table("inspection_templates")
    op.drop_table("safety_corrective_actions")
    op.drop_table("safety_records")
    op.drop_table("safety_project_counters")
