"""Create versioned custom field metadata.

Revision ID: 20260910_0006
Revises: 20260910_0005
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0006"
down_revision: str | None = "20260910_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_KEYS = (
    "admin.custom_field.view",
    "admin.custom_field.manage",
)

FIELD_TYPES = (
    "text",
    "long_text",
    "integer",
    "decimal",
    "currency",
    "boolean",
    "date",
    "datetime",
    "single_select",
    "multi_select",
    "user",
    "company",
    "project",
    "phone",
    "email",
    "url",
    "attachment",
    "measurement",
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
                "key": "admin.custom_field.view",
                "module": "admin",
                "resource": "custom_field",
                "action": "view",
                "description": "View custom field definitions and configuration.",
                "risk": "medium",
                "is_active": True,
            },
            {
                "key": "admin.custom_field.manage",
                "module": "admin",
                "resource": "custom_field",
                "action": "manage",
                "description": "Create, change, retire, and configure custom field definitions.",
                "risk": "high",
                "is_active": True,
            },
        ],
    )

    op.create_table(
        "custom_field_definitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "field_type",
            sa.Enum(*FIELD_TYPES, name="customfieldtype", native_enum=False),
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "validation_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("searchable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("filterable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reportable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("editable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("view_permission_key", sa.String(length=160), nullable=True),
        sa.Column("edit_permission_key", sa.String(length=160), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.CheckConstraint(
            "display_order >= 0", name="ck_custom_field_definitions_display_order"
        ),
        sa.CheckConstraint("version >= 1", name="ck_custom_field_definitions_version"),
        sa.ForeignKeyConstraint(
            ["edit_permission_key"],
            ["permissions.key"],
            name=op.f("fk_custom_field_definitions_edit_permission_key_permissions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_custom_field_definitions_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["view_permission_key"],
            ["permissions.key"],
            name=op.f("fk_custom_field_definitions_view_permission_key_permissions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_field_definitions")),
        sa.UniqueConstraint(
            "organization_id",
            "entity_type",
            "key",
            name="uq_custom_field_definitions_org_entity_key",
        ),
    )
    op.create_index(
        op.f("ix_custom_field_definitions_organization_id"),
        "custom_field_definitions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_definitions_entity_type"),
        "custom_field_definitions",
        ["entity_type"],
        unique=False,
    )

    op.create_table(
        "custom_field_options",
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.CheckConstraint("display_order >= 0", name="ck_custom_field_options_display_order"),
        sa.CheckConstraint("version >= 1", name="ck_custom_field_options_version"),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f("fk_custom_field_options_definition_id_custom_field_definitions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_field_options")),
        sa.UniqueConstraint(
            "definition_id", "key", name="uq_custom_field_options_definition_key"
        ),
    )
    op.create_index(
        op.f("ix_custom_field_options_definition_id"),
        "custom_field_options",
        ["definition_id"],
        unique=False,
    )

    op.create_table(
        "custom_field_definition_revisions",
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "version >= 1", name="ck_custom_field_definition_revisions_version"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_custom_field_definition_revisions_changed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f(
                "fk_custom_field_definition_revisions_definition_id_custom_field_definitions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_custom_field_definition_revisions_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "definition_id", "version", name=op.f("pk_custom_field_definition_revisions")
        ),
    )
    op.create_index(
        op.f("ix_custom_field_definition_revisions_organization_id"),
        "custom_field_definition_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_definition_revisions_changed_at"),
        "custom_field_definition_revisions",
        ["changed_at"],
        unique=False,
    )

    op.create_table(
        "custom_field_values",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("numeric_value", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("date_value", sa.Date(), nullable=True),
        sa.Column("datetime_value", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uuid_value", sa.Uuid(), nullable=True),
        sa.Column("json_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.Column("unit_code", sa.String(length=32), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint(
            "definition_version >= 1", name="ck_custom_field_values_definition_version"
        ),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f("fk_custom_field_values_definition_id_custom_field_definitions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_custom_field_values_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_custom_field_values_updated_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_field_values")),
        sa.UniqueConstraint(
            "organization_id",
            "definition_id",
            "entity_id",
            name="uq_custom_field_values_org_definition_entity",
        ),
    )
    op.create_index(
        op.f("ix_custom_field_values_organization_id"),
        "custom_field_values",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_values_definition_id"),
        "custom_field_values",
        ["definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_values_entity_id"),
        "custom_field_values",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_custom_field_values_org_entity",
        "custom_field_values",
        ["organization_id", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_custom_field_values_org_entity", table_name="custom_field_values")
    op.drop_index(op.f("ix_custom_field_values_entity_id"), table_name="custom_field_values")
    op.drop_index(
        op.f("ix_custom_field_values_definition_id"), table_name="custom_field_values"
    )
    op.drop_index(
        op.f("ix_custom_field_values_organization_id"), table_name="custom_field_values"
    )
    op.drop_table("custom_field_values")

    op.drop_index(
        op.f("ix_custom_field_definition_revisions_changed_at"),
        table_name="custom_field_definition_revisions",
    )
    op.drop_index(
        op.f("ix_custom_field_definition_revisions_organization_id"),
        table_name="custom_field_definition_revisions",
    )
    op.drop_table("custom_field_definition_revisions")

    op.drop_index(
        op.f("ix_custom_field_options_definition_id"), table_name="custom_field_options"
    )
    op.drop_table("custom_field_options")

    op.drop_index(
        op.f("ix_custom_field_definitions_entity_type"), table_name="custom_field_definitions"
    )
    op.drop_index(
        op.f("ix_custom_field_definitions_organization_id"),
        table_name="custom_field_definitions",
    )
    op.drop_table("custom_field_definitions")

    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(permissions.delete().where(permissions.c.key.in_(PERMISSION_KEYS)))
