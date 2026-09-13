"""Add India estimating, rate analysis and budget foundation.

Revision ID: 20260910_0037
Revises: 20260910_0036
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0037"
down_revision: str | None = "20260910_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("estimating.module.view", "module", "view", "Access estimating and budget controls.", "medium"),
    ("estimating.estimate.view", "estimate", "view", "View project estimates and rate analyses.", "high"),
    ("estimating.estimate.manage", "estimate", "manage", "Create and revise draft estimates.", "high"),
    ("estimating.estimate.submit", "estimate", "submit", "Submit project estimates for approval.", "high"),
    ("estimating.estimate.approve", "estimate", "approve", "Approve project estimates.", "critical"),
    ("estimating.rate_analysis.manage", "rate_analysis", "manage", "Create versioned rate analyses.", "high"),
    ("estimating.budget.view", "budget", "view", "View project budget baselines.", "high"),
    ("estimating.budget.manage", "budget", "manage", "Create and revise draft project budgets.", "high"),
    ("estimating.budget.approve", "budget", "approve", "Approve a project budget baseline.", "critical"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "project_estimates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_boq_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column(
            "status",
            sa.Enum("draft", "submitted", "approved", "superseded", "cancelled", name="estimatestatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_estimates_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_estimates_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_boq_id", "project_id", "organization_id"],
            ["project_boqs.id", "project_boqs.project_id", "project_boqs.organization_id"],
            name="fk_project_estimates_boq_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_estimates_approved_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_estimates"),
        sa.UniqueConstraint("project_id", "code", name="uq_project_estimates_project_code"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_project_estimates_scope"),
    )
    op.create_index("ix_project_estimates_project_status", "project_estimates", ["project_id", "status"])
    op.create_index("ix_project_estimates_organization_id", "project_estimates", ["organization_id"])
    op.create_index("ix_project_estimates_source_boq_id", "project_estimates", ["source_boq_id"])

    op.create_table(
        "estimate_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name="ck_estimate_items_quantity"),
        sa.CheckConstraint("rate >= 0", name="ck_estimate_items_rate"),
        sa.CheckConstraint("amount >= 0", name="ck_estimate_items_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_estimate_items_revision"),
        sa.ForeignKeyConstraint(
            ["estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_items_estimate_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_estimate_items_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_estimate_items_boq_item_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_estimate_items"),
        sa.UniqueConstraint("estimate_id", "line_number", name="uq_estimate_items_line"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_estimate_items_scope"),
    )
    op.create_index("ix_estimate_items_project_wbs", "estimate_items", ["project_id", "wbs_code_id"])
    op.create_index("ix_estimate_items_estimate_id", "estimate_items", ["estimate_id"])

    op.create_table(
        "rate_analyses",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_item_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("wastage_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("overhead_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("profit_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("calculated_rate", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version_number >= 1", name="ck_rate_analyses_version"),
        sa.CheckConstraint("wastage_percent >= 0", name="ck_rate_analyses_wastage"),
        sa.CheckConstraint("overhead_percent >= 0", name="ck_rate_analyses_overhead"),
        sa.CheckConstraint("profit_percent >= 0", name="ck_rate_analyses_profit"),
        sa.CheckConstraint("calculated_rate >= 0", name="ck_rate_analyses_rate"),
        sa.ForeignKeyConstraint(
            ["estimate_item_id", "project_id", "organization_id"],
            ["estimate_items.id", "estimate_items.project_id", "estimate_items.organization_id"],
            name="fk_rate_analyses_estimate_item_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rate_analyses"),
        sa.UniqueConstraint("estimate_item_id", "version_number", name="uq_rate_analysis_item_version"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_rate_analyses_scope"),
    )
    op.create_index("ix_rate_analyses_estimate_item_id", "rate_analyses", ["estimate_item_id"])

    op.create_table(
        "rate_analysis_components",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("material", "labour", "equipment", "subcontract", "overhead", "other", name="ratecomponentkind", native_enum=False),
            nullable=False,
        ),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="1"),
        sa.Column("unit_rate", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("source_entity_type", sa.String(80), nullable=True),
        sa.Column("source_entity_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name="ck_rate_components_quantity"),
        sa.CheckConstraint("unit_rate >= 0", name="ck_rate_components_unit_rate"),
        sa.CheckConstraint("amount >= 0", name="ck_rate_components_amount"),
        sa.ForeignKeyConstraint(
            ["analysis_id", "project_id", "organization_id"],
            ["rate_analyses.id", "rate_analyses.project_id", "rate_analyses.organization_id"],
            name="fk_rate_components_analysis_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rate_analysis_components"),
    )
    op.create_index("ix_rate_components_analysis_kind", "rate_analysis_components", ["analysis_id", "kind"])

    op.create_table(
        "project_budgets",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column(
            "status",
            sa.Enum("draft", "approved", "superseded", "cancelled", name="budgetstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_budgets_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_budgets_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_project_budgets_estimate_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_budgets_approved_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_budgets"),
        sa.UniqueConstraint("project_id", "code", name="uq_project_budgets_project_code"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_project_budgets_scope"),
    )
    op.create_index("ix_project_budgets_project_status", "project_budgets", ["project_id", "status"])

    op.create_table(
        "project_budget_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("budget_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=False),
        sa.Column(
            "category",
            sa.Enum("material", "labour", "equipment", "subcontract", "overhead", "other", name="budgetcategory", native_enum=False),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount >= 0", name="ck_budget_lines_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_budget_lines_revision"),
        sa.ForeignKeyConstraint(
            ["budget_id", "project_id", "organization_id"],
            ["project_budgets.id", "project_budgets.project_id", "project_budgets.organization_id"],
            name="fk_budget_lines_budget_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_budget_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_budget_lines"),
        sa.UniqueConstraint("budget_id", "wbs_code_id", "category", name="uq_budget_line_dimension"),
    )
    op.create_index("ix_budget_lines_project_wbs", "project_budget_lines", ["project_id", "wbs_code_id"])

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
                "module": "estimating",
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
    keys = ",".join(f"'{item[0]}'" for item in _PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM permissions WHERE key IN ({keys})"))
    op.drop_table("project_budget_lines")
    op.drop_table("project_budgets")
    op.drop_table("rate_analysis_components")
    op.drop_table("rate_analyses")
    op.drop_table("estimate_items")
    op.drop_table("project_estimates")
