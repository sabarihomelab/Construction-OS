"""Add hierarchical company and project configuration foundation.

Revision ID: 20260910_0029
Revises: 20260910_0028
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0029"
down_revision: str | None = "20260910_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIGURATION_PERMISSIONS = (
    (
        "admin.configuration.view",
        "admin",
        "configuration",
        "view",
        "View registered company, project-template and project configuration definitions and effective values.",
        "high",
    ),
    (
        "admin.configuration.manage",
        "admin",
        "configuration",
        "manage",
        "Create versioned company, project-template and project configuration overrides.",
        "critical",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "organization_configuration_states",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_organization_configuration_states_revision",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_configuration_states_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            name="pk_organization_configuration_states",
        ),
    )

    op.create_table(
        "configuration_values",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("module_key", sa.String(length=80), nullable=False),
        sa.Column("configuration_key", sa.String(length=180), nullable=False),
        sa.Column(
            "scope_type",
            sa.Enum(
                "company",
                "project_template",
                "project",
                name="configurationscopetype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.CheckConstraint(
            "current_version >= 1",
            name="ck_configuration_values_current_version",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_configuration_values_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_configuration_values"),
        sa.UniqueConstraint("id", "organization_id", name="uq_configuration_values_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "module_key",
            "configuration_key",
            "scope_type",
            "scope_id",
            name="uq_configuration_values_scope_key",
        ),
    )
    op.create_index(
        "ix_configuration_values_organization_id",
        "configuration_values",
        ["organization_id"],
    )
    op.create_index("ix_configuration_values_module_key", "configuration_values", ["module_key"])
    op.create_index(
        "ix_configuration_values_configuration_key",
        "configuration_values",
        ["configuration_key"],
    )
    op.create_index("ix_configuration_values_scope_type", "configuration_values", ["scope_type"])
    op.create_index("ix_configuration_values_scope_id", "configuration_values", ["scope_id"])
    op.create_index(
        "ix_configuration_values_resolution",
        "configuration_values",
        ["organization_id", "module_key", "scope_type", "scope_id"],
    )

    op.create_table(
        "configuration_value_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("configuration_value_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "change_class",
            sa.Enum(
                "presentation",
                "metadata",
                "business_rule",
                "workflow",
                "financial",
                "security",
                name="configurationchangeclass",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_configuration_value_versions_version"),
        sa.ForeignKeyConstraint(
            ["configuration_value_id", "organization_id"],
            ["configuration_values.id", "configuration_values.organization_id"],
            name="fk_configuration_value_versions_value_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name="fk_configuration_value_versions_changed_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_configuration_value_versions"),
        sa.UniqueConstraint(
            "configuration_value_id",
            "version",
            name="uq_configuration_value_versions_value_version",
        ),
    )
    op.create_index(
        "ix_configuration_value_versions_organization_id",
        "configuration_value_versions",
        ["organization_id"],
    )
    op.create_index(
        "ix_configuration_value_versions_configuration_value_id",
        "configuration_value_versions",
        ["configuration_value_id"],
    )
    op.create_index(
        "ix_configuration_value_versions_effective_from",
        "configuration_value_versions",
        ["effective_from"],
    )
    op.create_index(
        "ix_configuration_value_versions_effective",
        "configuration_value_versions",
        ["configuration_value_id", "effective_from", "version"],
    )

    op.create_table(
        "configuration_scope_revisions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("module_key", sa.String(length=80), nullable=False),
        sa.Column(
            "scope_type",
            sa.Enum(
                "company",
                "project_template",
                "project",
                name="configurationscopetype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_configuration_scope_revisions_revision",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_configuration_scope_revisions_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "module_key",
            "scope_type",
            "scope_id",
            name="pk_configuration_scope_revisions",
        ),
    )

    op.create_table(
        "membership_preference_states",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_membership_preference_states_revision",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_membership_preference_states_membership_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("membership_id", name="pk_membership_preference_states"),
    )
    op.create_index(
        "ix_membership_preference_states_organization_id",
        "membership_preference_states",
        ["organization_id"],
    )

    op.create_table(
        "membership_preferences",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("module_key", sa.String(length=80), nullable=False),
        sa.Column("preference_key", sa.String(length=180), nullable=False),
        sa.Column(
            "context_type",
            sa.Enum(
                "company",
                "project",
                name="preferencecontexttype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("context_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_membership_preferences_version"),
        sa.CheckConstraint(
            "(context_type = 'company' AND project_id IS NULL AND context_id = organization_id) OR "
            "(context_type = 'project' AND project_id IS NOT NULL AND context_id = project_id)",
            name="ck_membership_preferences_context",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_membership_preferences_membership_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_membership_preferences_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_membership_preferences_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_membership_preferences"),
        sa.UniqueConstraint(
            "organization_id",
            "membership_id",
            "module_key",
            "preference_key",
            "context_type",
            "context_id",
            name="uq_membership_preferences_context_key",
        ),
    )
    op.create_index(
        "ix_membership_preferences_organization_id",
        "membership_preferences",
        ["organization_id"],
    )
    op.create_index("ix_membership_preferences_membership_id", "membership_preferences", ["membership_id"])
    op.create_index("ix_membership_preferences_module_key", "membership_preferences", ["module_key"])
    op.create_index("ix_membership_preferences_preference_key", "membership_preferences", ["preference_key"])
    op.create_index("ix_membership_preferences_context_id", "membership_preferences", ["context_id"])
    op.create_index("ix_membership_preferences_project_id", "membership_preferences", ["project_id"])
    op.create_index(
        "ix_membership_preferences_resolution",
        "membership_preferences",
        ["organization_id", "membership_id", "module_key", "context_type", "context_id"],
    )

    op.add_column(
        "projects",
        sa.Column("configuration_template_version_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_projects_configuration_template_version_id",
        "projects",
        ["configuration_template_version_id"],
    )
    op.create_foreign_key(
        "fk_projects_configuration_template_version_org",
        "projects",
        "configuration_template_versions",
        ["configuration_template_version_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )

    permission_table = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
        sa.column("risk", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permission_table,
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
            for key, module, resource, action, description, risk in _CONFIGURATION_PERMISSIONS
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE key IN "
            "('admin.configuration.view', 'admin.configuration.manage')"
        )
    )
    op.drop_constraint(
        "fk_projects_configuration_template_version_org",
        "projects",
        type_="foreignkey",
    )
    op.drop_index("ix_projects_configuration_template_version_id", table_name="projects")
    op.drop_column("projects", "configuration_template_version_id")
    op.drop_table("membership_preferences")
    op.drop_table("membership_preference_states")
    op.drop_table("configuration_scope_revisions")
    op.drop_table("configuration_value_versions")
    op.drop_table("configuration_values")
    op.drop_table("organization_configuration_states")
