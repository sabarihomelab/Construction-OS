"""Add India commercial control core.

Revision ID: 20260910_0036
Revises: 20260910_0035
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0036"
down_revision: str | None = "20260910_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("commercial.module.view", "module", "view", "Access India commercial controls within authorized projects.", "medium"),
    ("commercial.party.view", "party", "view", "View company parties and project party assignments.", "medium"),
    ("commercial.party.manage", "party", "manage", "Create and maintain parties and project party assignments.", "high"),
    ("commercial.wbs.view", "wbs", "view", "View project WBS and cost-code structures.", "medium"),
    ("commercial.wbs.manage", "wbs", "manage", "Create and revise project WBS and cost-code structures.", "high"),
    ("commercial.boq.view", "boq", "view", "View BOQs and approved commercial baselines.", "high"),
    ("commercial.boq.manage", "boq", "manage", "Create and revise draft BOQs and BOQ items.", "high"),
    ("commercial.boq.approve", "boq", "approve", "Approve a BOQ baseline and create an immutable snapshot.", "critical"),
    ("commercial.measurement.view", "measurement", "view", "View project measurement-book entries.", "high"),
    ("commercial.measurement.create", "measurement", "create", "Record project quantities against approved BOQ items.", "high"),
    ("commercial.measurement.submit", "measurement", "submit", "Submit measured quantities for certification.", "high"),
    ("commercial.measurement.certify", "measurement", "certify", "Certify or reject submitted measured quantities.", "critical"),
    ("commercial.ra_bill.view", "ra_bill", "view", "View RA bills and their certified measurement basis.", "high"),
    ("commercial.ra_bill.create", "ra_bill", "create", "Prepare RA bills from unbilled certified measurements.", "high"),
    ("commercial.ra_bill.submit", "ra_bill", "submit", "Submit an RA bill for certification.", "critical"),
    ("commercial.ra_bill.certify", "ra_bill", "certify", "Certify RA bills and record payment state transitions.", "critical"),
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
    op.create_table(
        "commercial_parties",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column(
            "party_type",
            sa.Enum(
                "client",
                "consultant",
                "subcontractor",
                "supplier",
                "labour_contractor",
                "other",
                name="partytype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="partystatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("pan", sa.String(10), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address_line_1", sa.String(255), nullable=True),
        sa.Column("address_line_2", sa.String(255), nullable=True),
        sa.Column("locality", sa.String(120), nullable=True),
        sa.Column("state_name", sa.String(120), nullable=True),
        sa.Column("state_code", sa.String(2), nullable=True),
        sa.Column("postal_code", sa.String(12), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_commercial_parties_revision"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_commercial_parties_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_commercial_parties"),
        sa.UniqueConstraint("organization_id", "code", name="uq_commercial_parties_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_commercial_parties_id_org"),
    )
    op.create_index(
        "ix_commercial_parties_org_type_status",
        "commercial_parties",
        ["organization_id", "party_type", "status"],
    )
    op.create_index(
        "ix_commercial_parties_organization_id",
        "commercial_parties",
        ["organization_id"],
    )

    op.create_table(
        "project_party_assignments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("party_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "client",
                "pmc",
                "consultant",
                "subcontractor",
                "supplier",
                "labour_contractor",
                "other",
                name="projectpartyrole",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_party_assignments_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_project_party_assignments_party_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_party_assignments"),
        sa.UniqueConstraint(
            "project_id",
            "party_id",
            "role",
            name="uq_project_party_assignment_role",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_project_party_assignment_scope",
        ),
    )
    op.create_index(
        "ix_project_party_assignments_project_role",
        "project_party_assignments",
        ["project_id", "role"],
    )
    op.create_index(
        "ix_project_party_assignments_organization_id",
        "project_party_assignments",
        ["organization_id"],
    )
    op.create_index(
        "ix_project_party_assignments_project_id",
        "project_party_assignments",
        ["project_id"],
    )
    op.create_index(
        "ix_project_party_assignments_party_id",
        "project_party_assignments",
        ["party_id"],
    )

    op.create_table(
        "project_wbs_codes",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "group",
                "trade",
                "work_package",
                "cost_code",
                name="wbskind",
                native_enum=False,
            ),
            nullable=False,
            server_default="cost_code",
        ),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="recordstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_wbs_codes_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_wbs_codes_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_project_wbs_codes_parent_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_wbs_codes"),
        sa.UniqueConstraint("project_id", "code", name="uq_project_wbs_codes_project_code"),
        sa.UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_project_wbs_codes_scope"
        ),
    )
    op.create_index(
        "ix_project_wbs_codes_project_parent",
        "project_wbs_codes",
        ["project_id", "parent_id"],
    )
    op.create_index(
        "ix_project_wbs_codes_organization_id", "project_wbs_codes", ["organization_id"]
    )
    op.create_index("ix_project_wbs_codes_project_id", "project_wbs_codes", ["project_id"])

    op.create_table(
        "project_boqs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "superseded",
                "cancelled",
                name="boqstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_project_boqs_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_boqs_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_boqs_approved_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_boqs"),
        sa.UniqueConstraint("project_id", "code", name="uq_project_boqs_project_code"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_project_boqs_scope"),
    )
    op.create_index("ix_project_boqs_project_status", "project_boqs", ["project_id", "status"])
    op.create_index("ix_project_boqs_organization_id", "project_boqs", ["organization_id"])
    op.create_index("ix_project_boqs_project_id", "project_boqs", ["project_id"])

    op.create_table(
        "project_boq_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("boq_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("hsn_sac", sa.String(16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name="ck_project_boq_items_quantity"),
        sa.CheckConstraint("rate >= 0", name="ck_project_boq_items_rate"),
        sa.CheckConstraint("amount >= 0", name="ck_project_boq_items_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_project_boq_items_revision"),
        sa.ForeignKeyConstraint(
            ["boq_id", "project_id", "organization_id"],
            ["project_boqs.id", "project_boqs.project_id", "project_boqs.organization_id"],
            name="fk_project_boq_items_boq_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_project_boq_items_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_boq_items"),
        sa.UniqueConstraint("boq_id", "line_number", name="uq_project_boq_items_line_number"),
        sa.UniqueConstraint("boq_id", "item_code", name="uq_project_boq_items_item_code"),
        sa.UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_project_boq_items_scope"
        ),
    )
    op.create_index(
        "ix_project_boq_items_project_wbs", "project_boq_items", ["project_id", "wbs_code_id"]
    )
    op.create_index("ix_project_boq_items_organization_id", "project_boq_items", ["organization_id"])
    op.create_index("ix_project_boq_items_project_id", "project_boq_items", ["project_id"])
    op.create_index("ix_project_boq_items_boq_id", "project_boq_items", ["boq_id"])
    op.create_index("ix_project_boq_items_wbs_code_id", "project_boq_items", ["wbs_code_id"])

    op.create_table(
        "project_boq_revisions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("boq_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version_number >= 1", name="ck_project_boq_revision_version"),
        sa.ForeignKeyConstraint(
            ["boq_id", "project_id", "organization_id"],
            ["project_boqs.id", "project_boqs.project_id", "project_boqs.organization_id"],
            name="fk_project_boq_revisions_boq_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_boq_revisions_approved_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_boq_revisions"),
        sa.UniqueConstraint("boq_id", "version_number", name="uq_project_boq_revision_version"),
    )
    op.create_index("ix_project_boq_revisions_boq_id", "project_boq_revisions", ["boq_id"])
    op.create_index(
        "ix_project_boq_revisions_organization_id", "project_boq_revisions", ["organization_id"]
    )
    op.create_index("ix_project_boq_revisions_project_id", "project_boq_revisions", ["project_id"])

    op.create_table(
        "measurement_entries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("boq_item_id", sa.Uuid(), nullable=False),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("measurement_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "certified",
                "rejected",
                name="measurementstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("recorded_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("certified_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name="ck_measurement_entries_quantity"),
        sa.CheckConstraint("revision >= 1", name="ck_measurement_entries_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_measurement_entries_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_measurement_entries_boq_item_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_measurement_entries_recorded_by_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["certified_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_measurement_entries_certified_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_measurement_entries"),
        sa.UniqueConstraint("project_id", "entry_number", name="uq_measurement_entries_project_number"),
        sa.UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_measurement_entries_scope"
        ),
    )
    op.create_index(
        "ix_measurement_entries_project_status_date",
        "measurement_entries",
        ["project_id", "status", "measurement_date"],
    )
    op.create_index("ix_measurement_entries_organization_id", "measurement_entries", ["organization_id"])
    op.create_index("ix_measurement_entries_project_id", "measurement_entries", ["project_id"])
    op.create_index("ix_measurement_entries_boq_item_id", "measurement_entries", ["boq_item_id"])

    op.create_table(
        "ra_bills",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("counterparty_id", sa.Uuid(), nullable=False),
        sa.Column("bill_number", sa.String(80), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "certified",
                "paid",
                "cancelled",
                name="rabillstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("retention_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column(
            "statutory_deduction_amount",
            sa.Numeric(20, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("other_deduction_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("net_payable", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certified_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_ra_bills_revision"),
        sa.CheckConstraint("gross_amount >= 0", name="ck_ra_bills_gross_amount"),
        sa.CheckConstraint("retention_amount >= 0", name="ck_ra_bills_retention_amount"),
        sa.CheckConstraint(
            "statutory_deduction_amount >= 0",
            name="ck_ra_bills_statutory_deduction_amount",
        ),
        sa.CheckConstraint("other_deduction_amount >= 0", name="ck_ra_bills_other_deduction_amount"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_ra_bills_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["counterparty_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_ra_bills_counterparty_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["certified_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_ra_bills_certified_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ra_bills"),
        sa.UniqueConstraint("project_id", "bill_number", name="uq_ra_bills_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_ra_bills_scope"),
    )
    op.create_index("ix_ra_bills_project_status", "ra_bills", ["project_id", "status"])
    op.create_index("ix_ra_bills_organization_id", "ra_bills", ["organization_id"])
    op.create_index("ix_ra_bills_project_id", "ra_bills", ["project_id"])
    op.create_index("ix_ra_bills_counterparty_id", "ra_bills", ["counterparty_id"])

    op.create_table(
        "ra_bill_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("ra_bill_id", sa.Uuid(), nullable=False),
        sa.Column("boq_item_id", sa.Uuid(), nullable=False),
        sa.Column("current_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("current_quantity >= 0", name="ck_ra_bill_lines_current_quantity"),
        sa.CheckConstraint("rate >= 0", name="ck_ra_bill_lines_rate"),
        sa.CheckConstraint("gross_amount >= 0", name="ck_ra_bill_lines_gross_amount"),
        sa.ForeignKeyConstraint(
            ["ra_bill_id", "project_id", "organization_id"],
            ["ra_bills.id", "ra_bills.project_id", "ra_bills.organization_id"],
            name="fk_ra_bill_lines_bill_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_ra_bill_lines_boq_item_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ra_bill_lines"),
        sa.UniqueConstraint("ra_bill_id", "boq_item_id", name="uq_ra_bill_lines_boq_item"),
    )
    op.create_index("ix_ra_bill_lines_organization_id", "ra_bill_lines", ["organization_id"])
    op.create_index("ix_ra_bill_lines_project_id", "ra_bill_lines", ["project_id"])
    op.create_index("ix_ra_bill_lines_ra_bill_id", "ra_bill_lines", ["ra_bill_id"])
    op.create_index("ix_ra_bill_lines_boq_item_id", "ra_bill_lines", ["boq_item_id"])

    op.create_table(
        "ra_bill_measurements",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("ra_bill_id", sa.Uuid(), nullable=False),
        sa.Column("measurement_entry_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["ra_bill_id", "project_id", "organization_id"],
            ["ra_bills.id", "ra_bills.project_id", "ra_bills.organization_id"],
            name="fk_ra_bill_measurements_bill_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["measurement_entry_id", "project_id", "organization_id"],
            ["measurement_entries.id", "measurement_entries.project_id", "measurement_entries.organization_id"],
            name="fk_ra_bill_measurements_entry_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ra_bill_measurements"),
        sa.UniqueConstraint("measurement_entry_id", name="uq_ra_bill_measurements_entry"),
    )
    op.create_index(
        "ix_ra_bill_measurements_organization_id", "ra_bill_measurements", ["organization_id"]
    )
    op.create_index("ix_ra_bill_measurements_project_id", "ra_bill_measurements", ["project_id"])
    op.create_index("ix_ra_bill_measurements_ra_bill_id", "ra_bill_measurements", ["ra_bill_id"])
    op.create_index(
        "ix_ra_bill_measurements_measurement_entry_id",
        "ra_bill_measurements",
        ["measurement_entry_id"],
    )

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
                "module": "commercial",
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
    op.drop_table("ra_bill_measurements")
    op.drop_table("ra_bill_lines")
    op.drop_table("ra_bills")
    op.drop_table("measurement_entries")
    op.drop_table("project_boq_revisions")
    op.drop_table("project_boq_items")
    op.drop_table("project_boqs")
    op.drop_table("project_wbs_codes")
    op.drop_table("project_party_assignments")
    op.drop_table("commercial_parties")
