"""Grant new attendance permissions to existing protected company administrators.

Revision ID: 20260911_0051
Revises: 20260911_0050
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0051"
down_revision: str | None = "20260911_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ATTENDANCE_PERMISSIONS = (
    "workforce.attendance.view",
    "workforce.attendance.create",
    "workforce.attendance.update",
    "workforce.attendance.submit",
    "workforce.attendance.approve",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_key)
            SELECT roles.id, permissions.key
            FROM roles
            CROSS JOIN permissions
            WHERE roles.organization_id IS NOT NULL
              AND roles.key = 'company-admin'
              AND roles.is_protected IS TRUE
              AND roles.is_active IS TRUE
              AND permissions.key = ANY(:permission_keys)
              AND permissions.is_active IS TRUE
            ON CONFLICT DO NOTHING
            """
        ).bindparams(permission_keys=list(_ATTENDANCE_PERMISSIONS))
    )
    op.execute(
        sa.text(
            """
            UPDATE organization_authorization_state AS state
            SET revision = state.revision + 1,
                updated_at = now()
            WHERE EXISTS (
                SELECT 1
                FROM roles
                WHERE roles.organization_id = state.organization_id
                  AND roles.key = 'company-admin'
                  AND roles.is_protected IS TRUE
                  AND roles.is_active IS TRUE
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions AS role_permission
            USING roles
            WHERE role_permission.role_id = roles.id
              AND roles.organization_id IS NOT NULL
              AND roles.key = 'company-admin'
              AND roles.is_protected IS TRUE
              AND role_permission.permission_key = ANY(:permission_keys)
            """
        ).bindparams(permission_keys=list(_ATTENDANCE_PERMISSIONS))
    )
    op.execute(
        sa.text(
            """
            UPDATE organization_authorization_state AS state
            SET revision = state.revision + 1,
                updated_at = now()
            WHERE EXISTS (
                SELECT 1
                FROM roles
                WHERE roles.organization_id = state.organization_id
                  AND roles.key = 'company-admin'
                  AND roles.is_protected IS TRUE
            )
            """
        )
    )
