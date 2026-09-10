"""Add workforce multi-project commercial context.

Revision ID: 20260911_0041
Revises: 20260910_0040
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0041"
down_revision: str | None = "20260910_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    (
        "workforce.rate.view",
        "rate",
        "view",
        "View permitted project worker commercial rates.",
        "high",
    ),
    (
        "workforce.rate.manage",
        "rate",
        "manage",
        "Create and retire effective-dated project worker commercial rates.",
        "critical",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
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
    op.add_column(
        "project_worker_assignments",
        sa.Column("employer_party_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "project_worker_assignments",
        sa.Column(
            "engagement_type",
            sa.Enum(
                "staff",
                "direct_labour",
                "contract_labour",
                "subcontractor_labour",
                "vendor_crew",
                "other",
                name="workerengagementtype",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_project_worker_assignments_employer_party_org",
        "project_worker_assignments",
        "commercial_parties",
        ["employer_party_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_project_worker_assignments_scope",
        "project_worker_assignments",
        ["id", "project_id", "organization_id"],
    )
    op.create_index(
        "ix_project_worker_assignments_employer",
        "project_worker_assignments",
        ["organization_id", "employer_party_id"],
    )

    op.create_table(
        "project_worker_rates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column(
            "wage_basis",
            sa.Enum(
                "hourly",
                "daily",
                "weekly",
                "monthly",
                "piece_rate",
                "contract",
                name="wagebasis",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("regular_rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("overtime_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("double_time_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("billing_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_worker_rates_revision"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_project_worker_rates_date_range",
        ),
        sa.CheckConstraint(
            "regular_rate >= 0", name="ck_project_worker_rates_regular_nonnegative"
        ),
        sa.CheckConstraint(
            "overtime_rate IS NULL OR overtime_rate >= 0",
            name="ck_project_worker_rates_overtime_nonnegative",
        ),
        sa.CheckConstraint(
            "double_time_rate IS NULL OR double_time_rate >= 0",
            name="ck_project_worker_rates_double_time_nonnegative",
        ),
        sa.CheckConstraint(
            "billing_rate IS NULL OR billing_rate >= 0",
            name="ck_project_worker_rates_billing_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "project_id", "organization_id"],
            [
                "project_worker_assignments.id",
                "project_worker_assignments.project_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_project_worker_rates_assignment_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "worker_id", "organization_id"],
            [
                "project_worker_assignments.project_id",
                "project_worker_assignments.worker_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_project_worker_rates_worker_assignment_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_worker_rates"),
        sa.UniqueConstraint(
            "assignment_id",
            "effective_from",
            name="uq_project_worker_rates_assignment_start",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_project_worker_rates_id_org"),
    )
    op.create_index(
        "ix_project_worker_rates_project_worker_date",
        "project_worker_rates",
        ["project_id", "worker_id", "effective_from"],
    )
    op.create_index(
        "ix_project_worker_rates_organization_id",
        "project_worker_rates",
        ["organization_id"],
    )
    op.create_index("ix_project_worker_rates_project_id", "project_worker_rates", ["project_id"])
    op.create_index(
        "ix_project_worker_rates_assignment_id",
        "project_worker_rates",
        ["assignment_id"],
    )
    op.create_index("ix_project_worker_rates_worker_id", "project_worker_rates", ["worker_id"])

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String),
        sa.column("module", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.Text),
        sa.column("risk", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": "workforce",
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
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(
        sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys)
    )
    op.drop_table("project_worker_rates")
    op.drop_index("ix_project_worker_assignments_employer", table_name="project_worker_assignments")
    op.drop_constraint(
        "uq_project_worker_assignments_scope",
        "project_worker_assignments",
        type_="unique",
    )
    op.drop_constraint(
        "fk_project_worker_assignments_employer_party_org",
        "project_worker_assignments",
        type_="foreignkey",
    )
    op.drop_column("project_worker_assignments", "engagement_type")
    op.drop_column("project_worker_assignments", "employer_party_id")
