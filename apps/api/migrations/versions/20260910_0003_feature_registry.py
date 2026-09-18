"""Create tenant feature overrides and initial permission catalog.

Revision ID: 20260910_0003
Revises: 20260910_0002
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0003"
down_revision: str | None = "20260910_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_KEYS = (
    "admin.settings.view",
    "admin.operations.view",
    "security.role.view",
    "security.role.manage",
    "help.content.view",
    "projects.project.view",
    "field.daily_log.view",
    "finance.budget.view",
)


def upgrade() -> None:
    op.create_table(
        "organization_features",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("feature_key", sa.String(length=160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_organization_features_version"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_features_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_organization_features_updated_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "feature_key", name=op.f("pk_organization_features")
        ),
    )

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
                "key": "admin.settings.view",
                "module": "admin",
                "resource": "settings",
                "action": "view",
                "description": "View company administration settings.",
                "risk": "medium",
                "is_active": True,
            },
            {
                "key": "admin.operations.view",
                "module": "admin",
                "resource": "operations",
                "action": "view",
                "description": "View company operational health and capacity information.",
                "risk": "high",
                "is_active": True,
            },
            {
                "key": "security.role.view",
                "module": "security",
                "resource": "role",
                "action": "view",
                "description": "View roles and their assigned capabilities.",
                "risk": "high",
                "is_active": True,
            },
            {
                "key": "security.role.manage",
                "module": "security",
                "resource": "role",
                "action": "manage",
                "description": "Create, update, clone, assign, and retire company roles.",
                "risk": "critical",
                "is_active": True,
            },
            {
                "key": "help.content.view",
                "module": "help",
                "resource": "content",
                "action": "view",
                "description": "View Construction OS help and product guidance.",
                "risk": "low",
                "is_active": True,
            },
            {
                "key": "projects.project.view",
                "module": "projects",
                "resource": "project",
                "action": "view",
                "description": "View projects within the authorized scope.",
                "risk": "medium",
                "is_active": True,
            },
            {
                "key": "field.daily_log.view",
                "module": "field",
                "resource": "daily_log",
                "action": "view",
                "description": "View daily logs within the authorized scope.",
                "risk": "medium",
                "is_active": True,
            },
            {
                "key": "finance.budget.view",
                "module": "finance",
                "resource": "budget",
                "action": "view",
                "description": "View project budget information within the authorized scope.",
                "risk": "high",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(permissions.delete().where(permissions.c.key.in_(PERMISSION_KEYS)))
    op.drop_table("organization_features")
