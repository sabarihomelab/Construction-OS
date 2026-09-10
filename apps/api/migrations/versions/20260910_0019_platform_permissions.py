"""Add remaining platform capability vocabulary.

Revision ID: 20260910_0019
Revises: 20260910_0018
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0019"
down_revision: str | None = "20260910_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("admin.operations.storage.view", "admin", "operations_storage", "view", "View storage usage and storage-health information.", "high"),
    ("admin.operations.security.view", "admin", "operations_security", "view", "View security-posture information exposed to company administrators.", "critical"),
    ("admin.operations.integrations.view", "admin", "operations_integrations", "view", "View integration and synchronization health.", "high"),
    ("admin.operations.audit.view", "admin", "operations_audit", "view", "View permitted operational audit diagnostics.", "critical"),
    ("admin.operations.manage", "admin", "operations", "manage", "Perform permitted operational remediation actions.", "critical"),
    ("integrations.connector.view", "integrations", "connector", "view", "View configured external-system connectors and sync status.", "high"),
    ("integrations.connector.manage", "integrations", "connector", "manage", "Configure, enable, disable, and reauthorize external-system connectors.", "critical"),
    ("integrations.sync.run", "integrations", "sync", "run", "Start an authorized connector synchronization or ingestion run.", "high"),
    ("reporting.report.view", "reporting", "report", "view", "View permitted reports and dashboards.", "medium"),
    ("reporting.report.create", "reporting", "report", "create", "Create personal or permitted shared saved views and reports.", "medium"),
    ("reporting.report.manage", "reporting", "report", "manage", "Publish and manage shared company report definitions and dashboards.", "high"),
    ("reporting.report.export", "reporting", "report", "export", "Generate permitted PDF, XLSX, or CSV report outputs.", "high"),
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
            {"key": key, "module": module, "resource": resource, "action": action, "description": description, "risk": risk, "is_active": True}
            for key, module, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in _PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")  # noqa: S608
