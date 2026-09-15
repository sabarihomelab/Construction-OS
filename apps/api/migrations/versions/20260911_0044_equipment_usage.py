"""Add governed equipment usage, rates, and operational permissions.

Revision ID: 20260911_0044
Revises: 20260911_0043
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0044"
down_revision: str | None = "20260911_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("equipment.usage.view", "equipment", "usage", "view", "View authoritative project equipment usage records.", "medium"),
    ("equipment.usage.create", "equipment", "usage", "create", "Create draft project equipment usage records.", "medium"),
    ("equipment.usage.post", "equipment", "usage", "post", "Post authoritative project equipment usage records.", "high"),
    ("equipment.rate.view", "equipment", "rate", "view", "View project equipment commercial cost rates.", "high"),
    ("equipment.rate.manage", "equipment", "rate", "manage", "Create and retire effective-dated project equipment commercial rates.", "critical"),
    ("materials.consumption.view", "materials", "consumption", "view", "View project material consumption records.", "medium"),
    ("materials.consumption.create", "materials", "consumption", "create", "Create draft project material consumption records.", "medium"),
    ("materials.consumption.post", "materials", "consumption", "post", "Post authoritative project material consumption and cost snapshots.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_equipment_assignments_scope",
        "project_equipment_assignments",
        ["id", "project_id", "organization_id"],
    )

    op.create_table(
        "project_equipment_rates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_assignment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "rate_basis",
            sa.Enum(
                "hourly",
                "daily",
                "monthly",
                "per_usage",
                name="equipmentratebasis",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("rate >= 0", name="ck_project_equipment_rates_rate"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_project_equipment_rates_date_range",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_project_equipment_rates_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_equipment_rates_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_assignment_id", "project_id", "organization_id"],
            [
                "project_equipment_assignments.id",
                "project_equipment_assignments.project_id",
                "project_equipment_assignments.organization_id",
            ],
            name="fk_project_equipment_rates_assignment_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_equipment_rates"),
        sa.UniqueConstraint(
            "equipment_assignment_id",
            "effective_from",
            name="uq_project_equipment_rates_assignment_start",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_project_equipment_rates_scope",
        ),
    )
    op.create_index(
        "ix_project_equipment_rates_organization_id",
        "project_equipment_rates",
        ["organization_id"],
    )
    op.create_index(
        "ix_project_equipment_rates_project_id",
        "project_equipment_rates",
        ["project_id"],
    )
    op.create_index(
        "ix_project_equipment_rates_equipment_assignment_id",
        "project_equipment_rates",
        ["equipment_assignment_id"],
    )
    op.create_index(
        "ix_project_equipment_rates_project_assignment_date",
        "project_equipment_rates",
        ["project_id", "equipment_assignment_id", "effective_from"],
    )

    op.create_table(
        "equipment_usages",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("shift_code", sa.String(40), nullable=False, server_default="day"),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("operating_hours", sa.Numeric(12, 4), nullable=True),
        sa.Column("meter_start", sa.Numeric(18, 4), nullable=True),
        sa.Column("meter_end", sa.Numeric(18, 4), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "posted",
                "reversed",
                name="equipmentusagestatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "operating_hours IS NULL OR operating_hours >= 0",
            name="ck_equipment_usages_operating_hours",
        ),
        sa.CheckConstraint(
            "meter_start IS NULL OR meter_start >= 0",
            name="ck_equipment_usages_meter_start",
        ),
        sa.CheckConstraint(
            "meter_end IS NULL OR meter_end >= 0",
            name="ck_equipment_usages_meter_end",
        ),
        sa.CheckConstraint(
            "(meter_start IS NULL AND meter_end IS NULL) OR "
            "(meter_start IS NOT NULL AND meter_end IS NOT NULL AND meter_end >= meter_start)",
            name="ck_equipment_usages_meter_pair",
        ),
        sa.CheckConstraint(
            "(operating_hours IS NOT NULL AND operating_hours > 0) OR "
            "(meter_start IS NOT NULL AND meter_end IS NOT NULL AND meter_end > meter_start)",
            name="ck_equipment_usages_observed_usage",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_equipment_usages_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_equipment_usages_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_assignment_id", "project_id", "organization_id"],
            [
                "project_equipment_assignments.id",
                "project_equipment_assignments.project_id",
                "project_equipment_assignments.organization_id",
            ],
            name="fk_equipment_usages_assignment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_equipment_usages_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_equipment_usages_boq_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_equipment_usages_creator_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "posted_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_equipment_usages_poster_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "reversed_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_equipment_usages_reverser_project_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_equipment_usages"),
        sa.UniqueConstraint(
            "project_id",
            "equipment_assignment_id",
            "usage_date",
            "shift_code",
            name="uq_equipment_usages_assignment_date_shift",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_equipment_usages_scope",
        ),
    )
    op.create_index("ix_equipment_usages_organization_id", "equipment_usages", ["organization_id"])
    op.create_index("ix_equipment_usages_project_id", "equipment_usages", ["project_id"])
    op.create_index(
        "ix_equipment_usages_equipment_assignment_id",
        "equipment_usages",
        ["equipment_assignment_id"],
    )
    op.create_index("ix_equipment_usages_wbs_code_id", "equipment_usages", ["wbs_code_id"])
    op.create_index("ix_equipment_usages_boq_item_id", "equipment_usages", ["boq_item_id"])
    op.create_index("ix_equipment_usages_project_date", "equipment_usages", ["project_id", "usage_date"])
    op.create_index(
        "ix_equipment_usages_project_assignment",
        "equipment_usages",
        ["project_id", "equipment_assignment_id"],
    )
    op.create_index(
        "ix_equipment_usages_project_status",
        "equipment_usages",
        ["project_id", "status"],
    )

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
                "module": module,
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, module, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys))
    op.drop_table("equipment_usages")
    op.drop_table("project_equipment_rates")
    op.drop_constraint(
        "uq_equipment_assignments_scope",
        "project_equipment_assignments",
        type_="unique",
    )
