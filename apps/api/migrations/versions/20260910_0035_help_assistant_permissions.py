"""Add India defaults and Construction OS Assistant permissions.

Revision ID: 20260910_0035
Revises: 20260910_0034
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0035"
down_revision: str | None = "20260910_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    (
        "help.assistant.use",
        "assistant",
        "use",
        "Use the permission-scoped Construction OS Assistant.",
        "medium",
    ),
    (
        "help.assistant.upgrade",
        "assistant",
        "upgrade_guidance",
        "Use installation, upgrade, migration and rollback guidance from the Construction OS Assistant.",
        "high",
    ),
)


def upgrade() -> None:
    # India is the Release 1 default for newly created rows. Existing organization
    # values are deliberately not rewritten by this migration.
    op.alter_column("organizations", "country_code", server_default="IN")
    op.alter_column("organization_settings", "locale", server_default="en-IN")
    op.alter_column("organization_settings", "timezone", server_default="Asia/Kolkata")
    op.alter_column("organization_settings", "base_currency", server_default="INR")

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
        sa.column("risk", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    statement = postgresql.insert(permissions).values(
        [
            {
                "key": key,
                "module": "help",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _PERMISSIONS
        ]
    )
    op.get_bind().execute(statement.on_conflict_do_nothing(index_elements=["key"]))


def downgrade() -> None:
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(
        permissions.delete().where(
            permissions.c.key.in_([key for key, *_ in _PERMISSIONS])
        )
    )
    op.alter_column("organization_settings", "base_currency", server_default="USD")
    op.alter_column("organization_settings", "timezone", server_default="UTC")
    op.alter_column("organization_settings", "locale", server_default="en-US")
    op.alter_column("organizations", "country_code", server_default=None)
