"""Add explicit role assignment scope.

Revision ID: 20260912_0055
Revises: 20260911_0054
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0055"
down_revision: str | None = "20260911_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column(
            "assignment_scope",
            sa.Enum(
                "company",
                "project",
                "both",
                name="roleassignmentscope",
                native_enum=False,
            ),
            nullable=False,
            server_default="both",
        ),
    )
    op.execute("UPDATE roles SET assignment_scope = 'company' WHERE key = 'company-admin'")


def downgrade() -> None:
    op.drop_column("roles", "assignment_scope")
