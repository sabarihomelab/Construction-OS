"""Create authorization foundation.

Revision ID: 20260910_0002
Revises: 20260910_0001
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260910_0002"
down_revision: str | None = "20260910_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("resource", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "risk",
            sa.Enum("low", "medium", "high", "critical", name="permissionrisk", native_enum=False),
            nullable=False,
            server_default="low",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_permissions")),
    )
    op.create_index(op.f("ix_permissions_module"), "permissions", ["module"], unique=False)

    op.create_table(
        "roles",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.CheckConstraint("version >= 1", name="ck_roles_version"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_roles_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
    )
    op.create_index(op.f("ix_roles_organization_id"), "roles", ["organization_id"], unique=False)
    op.create_index(
        "uq_roles_org_key",
        "roles",
        ["organization_id", "key"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )
    op.create_index(
        "uq_roles_system_template_key",
        "roles",
        ["key"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NULL"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_key", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_key"],
            ["permissions.key"],
            name=op.f("fk_role_permissions_permission_key_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_key", name=op.f("pk_role_permissions")),
    )

    op.create_table(
        "membership_roles",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["organization_memberships.id"],
            name=op.f("fk_membership_roles_membership_id_organization_memberships"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_membership_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("membership_id", "role_id", name=op.f("pk_membership_roles")),
    )

    op.create_table(
        "organization_authorization_state",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("revision >= 1", name="ck_organization_authorization_state_revision"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_authorization_state_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", name=op.f("pk_organization_authorization_state")
        ),
    )


def downgrade() -> None:
    op.drop_table("organization_authorization_state")
    op.drop_table("membership_roles")
    op.drop_table("role_permissions")
    op.drop_index("uq_roles_system_template_key", table_name="roles")
    op.drop_index("uq_roles_org_key", table_name="roles")
    op.drop_index(op.f("ix_roles_organization_id"), table_name="roles")
    op.drop_table("roles")
    op.drop_index(op.f("ix_permissions_module"), table_name="permissions")
    op.drop_table("permissions")
