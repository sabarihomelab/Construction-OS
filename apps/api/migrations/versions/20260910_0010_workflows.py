"""Create workflow and approval engine foundation.

Revision ID: 20260910_0010
Revises: 20260910_0009
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0010"
down_revision: str | None = "20260910_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WORKFLOW_PERMISSIONS = (
    (
        "admin.workflow.view",
        "admin",
        "workflow",
        "view",
        "View company workflow definitions, versions, states, and transitions.",
        "medium",
    ),
    (
        "admin.workflow.manage",
        "admin",
        "workflow",
        "manage",
        "Create, version, publish, retire, and configure company workflows.",
        "high",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


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
            for key, module, resource, action, description, risk in _WORKFLOW_PERMISSIONS
        ],
    )

    op.create_table(
        "workflow_definitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("current_version >= 0", name="ck_workflow_definitions_current_version"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE",
            name=op.f("fk_workflow_definitions_organization_id_organizations")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_workflow_definitions_created_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_definitions")),
        sa.UniqueConstraint("organization_id", "key", name="uq_workflow_definitions_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_workflow_definitions_id_org"),
    )
    op.create_index(op.f("ix_workflow_definitions_organization_id"), "workflow_definitions", ["organization_id"])
    op.create_index(op.f("ix_workflow_definitions_entity_type"), "workflow_definitions", ["entity_type"])
    op.create_index("ix_workflow_definitions_org_entity", "workflow_definitions", ["organization_id", "entity_type"])

    op.create_table(
        "workflow_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "retired", name="workflowversionstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_workflow_versions_version"),
        sa.ForeignKeyConstraint(
            ["definition_id", "organization_id"],
            ["workflow_definitions.id", "workflow_definitions.organization_id"],
            name="fk_workflow_versions_definition_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_workflow_versions_published_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_versions")),
        sa.UniqueConstraint("definition_id", "version", name="uq_workflow_versions_definition_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_workflow_versions_id_org"),
        sa.UniqueConstraint("id", "organization_id", "definition_id", name="uq_workflow_versions_id_org_definition"),
    )
    op.create_index(op.f("ix_workflow_versions_organization_id"), "workflow_versions", ["organization_id"])
    op.create_index(op.f("ix_workflow_versions_definition_id"), "workflow_versions", ["definition_id"])
    op.create_index("ix_workflow_versions_org_status", "workflow_versions", ["organization_id", "status"])

    op.create_table(
        "workflow_states",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("initial", "active", "completed", "cancelled", name="workflowstatekind", native_enum=False),
            nullable=False,
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.CheckConstraint("display_order >= 0", name="ck_workflow_states_display_order"),
        sa.ForeignKeyConstraint(
            ["workflow_version_id", "organization_id"],
            ["workflow_versions.id", "workflow_versions.organization_id"],
            name="fk_workflow_states_version_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_states")),
        sa.UniqueConstraint("workflow_version_id", "key", name="uq_workflow_states_version_key"),
        sa.UniqueConstraint("workflow_version_id", "key", "organization_id", name="uq_workflow_states_version_key_org"),
    )
    op.create_index(op.f("ix_workflow_states_organization_id"), "workflow_states", ["organization_id"])
    op.create_index(op.f("ix_workflow_states_workflow_version_id"), "workflow_states", ["workflow_version_id"])

    op.create_table(
        "workflow_transitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("from_state_key", sa.String(length=100), nullable=False),
        sa.Column("to_state_key", sa.String(length=100), nullable=False),
        sa.Column("required_permission_key", sa.String(length=160), nullable=True),
        sa.Column("requires_reason", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_step_up_mfa", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("assignment_rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("due_rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.CheckConstraint("from_state_key <> to_state_key", name="ck_workflow_transitions_state_change"),
        sa.ForeignKeyConstraint(
            ["workflow_version_id", "organization_id"],
            ["workflow_versions.id", "workflow_versions.organization_id"],
            name="fk_workflow_transitions_version_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id", "from_state_key", "organization_id"],
            ["workflow_states.workflow_version_id", "workflow_states.key", "workflow_states.organization_id"],
            name="fk_workflow_transitions_from_state",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id", "to_state_key", "organization_id"],
            ["workflow_states.workflow_version_id", "workflow_states.key", "workflow_states.organization_id"],
            name="fk_workflow_transitions_to_state",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["required_permission_key"], ["permissions.key"], ondelete="RESTRICT",
            name=op.f("fk_workflow_transitions_required_permission_key_permissions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transitions")),
        sa.UniqueConstraint("workflow_version_id", "key", name="uq_workflow_transitions_version_key"),
    )
    op.create_index(op.f("ix_workflow_transitions_organization_id"), "workflow_transitions", ["organization_id"])
    op.create_index(op.f("ix_workflow_transitions_workflow_version_id"), "workflow_transitions", ["workflow_version_id"])
    op.create_index("ix_workflow_transitions_version_from", "workflow_transitions", ["workflow_version_id", "from_state_key"])

    op.create_table(
        "workflow_instances",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("current_state_key", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "cancelled", name="workflowinstancestatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_workflow_instances_version"),
        sa.ForeignKeyConstraint(
            ["definition_id", "organization_id"],
            ["workflow_definitions.id", "workflow_definitions.organization_id"],
            name="fk_workflow_instances_definition_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id", "organization_id", "definition_id"],
            ["workflow_versions.id", "workflow_versions.organization_id", "workflow_versions.definition_id"],
            name="fk_workflow_instances_version_org_definition",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id", "current_state_key", "organization_id"],
            ["workflow_states.workflow_version_id", "workflow_states.key", "workflow_states.organization_id"],
            name="fk_workflow_instances_current_state",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["started_by_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_workflow_instances_started_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_instances")),
        sa.UniqueConstraint("organization_id", "definition_id", "entity_type", "entity_id", name="uq_workflow_instances_org_definition_entity"),
        sa.UniqueConstraint("id", "organization_id", name="uq_workflow_instances_id_org"),
    )
    op.create_index(op.f("ix_workflow_instances_organization_id"), "workflow_instances", ["organization_id"])
    op.create_index(op.f("ix_workflow_instances_definition_id"), "workflow_instances", ["definition_id"])
    op.create_index(op.f("ix_workflow_instances_workflow_version_id"), "workflow_instances", ["workflow_version_id"])
    op.create_index(op.f("ix_workflow_instances_entity_type"), "workflow_instances", ["entity_type"])
    op.create_index(op.f("ix_workflow_instances_entity_id"), "workflow_instances", ["entity_id"])
    op.create_index(op.f("ix_workflow_instances_current_state_key"), "workflow_instances", ["current_state_key"])
    op.create_index("ix_workflow_instances_org_entity", "workflow_instances", ["organization_id", "entity_type", "entity_id"])
    op.create_index("ix_workflow_instances_org_status", "workflow_instances", ["organization_id", "status"])

    op.create_table(
        "workflow_transition_requests",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=False),
        sa.Column("transition_key", sa.String(length=100), nullable=False),
        sa.Column("from_state_key", sa.String(length=100), nullable=False),
        sa.Column("to_state_key", sa.String(length=100), nullable=False),
        sa.Column("expected_instance_version", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "cancelled", "executed", name="transitionrequeststatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("expected_instance_version >= 1", name="ck_workflow_transition_requests_expected_version"),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_workflow_transition_requests_instance_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_workflow_transition_requests_requested_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transition_requests")),
        sa.UniqueConstraint("id", "organization_id", name="uq_workflow_transition_requests_id_org"),
    )
    op.create_index(op.f("ix_workflow_transition_requests_organization_id"), "workflow_transition_requests", ["organization_id"])
    op.create_index(op.f("ix_workflow_transition_requests_workflow_instance_id"), "workflow_transition_requests", ["workflow_instance_id"])
    op.create_index("ix_workflow_transition_requests_org_status", "workflow_transition_requests", ["organization_id", "status"])

    op.create_table(
        "workflow_approval_tasks",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("transition_request_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "assignee_type",
            sa.Enum("user", "role", "project_role", "external", name="approvalassigneetype", native_enum=False),
            nullable=False,
        ),
        sa.Column("assignee_id", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "cancelled", name="approvaltaskstatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_workflow_approval_tasks_sequence"),
        sa.ForeignKeyConstraint(
            ["transition_request_id", "organization_id"],
            ["workflow_transition_requests.id", "workflow_transition_requests.organization_id"],
            name="fk_workflow_approval_tasks_request_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_workflow_approval_tasks_decided_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_approval_tasks")),
        sa.UniqueConstraint("transition_request_id", "sequence", "assignee_type", "assignee_id", name="uq_workflow_approval_tasks_request_assignee"),
    )
    op.create_index(op.f("ix_workflow_approval_tasks_organization_id"), "workflow_approval_tasks", ["organization_id"])
    op.create_index(op.f("ix_workflow_approval_tasks_transition_request_id"), "workflow_approval_tasks", ["transition_request_id"])
    op.create_index("ix_workflow_approval_tasks_org_status", "workflow_approval_tasks", ["organization_id", "status"])
    op.create_index("ix_workflow_approval_tasks_assignee", "workflow_approval_tasks", ["organization_id", "assignee_type", "assignee_id", "status"])

    op.create_table(
        "workflow_history_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=False),
        sa.Column("instance_version", sa.BigInteger(), nullable=False),
        sa.Column("transition_key", sa.String(length=100), nullable=False),
        sa.Column("from_state_key", sa.String(length=100), nullable=False),
        sa.Column("to_state_key", sa.String(length=100), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("event_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("instance_version >= 1", name="ck_workflow_history_instance_version"),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_workflow_history_events_instance_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_workflow_history_events_actor_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_history_events")),
        sa.UniqueConstraint("workflow_instance_id", "instance_version", name="uq_workflow_history_instance_version"),
    )
    op.create_index(op.f("ix_workflow_history_events_organization_id"), "workflow_history_events", ["organization_id"])
    op.create_index(op.f("ix_workflow_history_events_workflow_instance_id"), "workflow_history_events", ["workflow_instance_id"])
    op.create_index(op.f("ix_workflow_history_events_occurred_at"), "workflow_history_events", ["occurred_at"])
    op.create_index(op.f("ix_workflow_history_events_correlation_id"), "workflow_history_events", ["correlation_id"])
    op.create_index("ix_workflow_history_org_occurred", "workflow_history_events", ["organization_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_history_org_occurred", table_name="workflow_history_events")
    op.drop_index(op.f("ix_workflow_history_events_correlation_id"), table_name="workflow_history_events")
    op.drop_index(op.f("ix_workflow_history_events_occurred_at"), table_name="workflow_history_events")
    op.drop_index(op.f("ix_workflow_history_events_workflow_instance_id"), table_name="workflow_history_events")
    op.drop_index(op.f("ix_workflow_history_events_organization_id"), table_name="workflow_history_events")
    op.drop_table("workflow_history_events")

    op.drop_index("ix_workflow_approval_tasks_assignee", table_name="workflow_approval_tasks")
    op.drop_index("ix_workflow_approval_tasks_org_status", table_name="workflow_approval_tasks")
    op.drop_index(op.f("ix_workflow_approval_tasks_transition_request_id"), table_name="workflow_approval_tasks")
    op.drop_index(op.f("ix_workflow_approval_tasks_organization_id"), table_name="workflow_approval_tasks")
    op.drop_table("workflow_approval_tasks")

    op.drop_index("ix_workflow_transition_requests_org_status", table_name="workflow_transition_requests")
    op.drop_index(op.f("ix_workflow_transition_requests_workflow_instance_id"), table_name="workflow_transition_requests")
    op.drop_index(op.f("ix_workflow_transition_requests_organization_id"), table_name="workflow_transition_requests")
    op.drop_table("workflow_transition_requests")

    op.drop_index("ix_workflow_instances_org_status", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_org_entity", table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_current_state_key"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_entity_id"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_entity_type"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_workflow_version_id"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_definition_id"), table_name="workflow_instances")
    op.drop_index(op.f("ix_workflow_instances_organization_id"), table_name="workflow_instances")
    op.drop_table("workflow_instances")

    op.drop_index("ix_workflow_transitions_version_from", table_name="workflow_transitions")
    op.drop_index(op.f("ix_workflow_transitions_workflow_version_id"), table_name="workflow_transitions")
    op.drop_index(op.f("ix_workflow_transitions_organization_id"), table_name="workflow_transitions")
    op.drop_table("workflow_transitions")

    op.drop_index(op.f("ix_workflow_states_workflow_version_id"), table_name="workflow_states")
    op.drop_index(op.f("ix_workflow_states_organization_id"), table_name="workflow_states")
    op.drop_table("workflow_states")

    op.drop_index("ix_workflow_versions_org_status", table_name="workflow_versions")
    op.drop_index(op.f("ix_workflow_versions_definition_id"), table_name="workflow_versions")
    op.drop_index(op.f("ix_workflow_versions_organization_id"), table_name="workflow_versions")
    op.drop_table("workflow_versions")

    op.drop_index("ix_workflow_definitions_org_entity", table_name="workflow_definitions")
    op.drop_index(op.f("ix_workflow_definitions_entity_type"), table_name="workflow_definitions")
    op.drop_index(op.f("ix_workflow_definitions_organization_id"), table_name="workflow_definitions")
    op.drop_table("workflow_definitions")

    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(
        permissions.delete().where(
            permissions.c.key.in_([permission[0] for permission in _WORKFLOW_PERMISSIONS])
        )
    )
