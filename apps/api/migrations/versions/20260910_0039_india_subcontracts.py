"""Add India subcontract and progress claim foundation.

Revision ID: 20260910_0039
Revises: 20260910_0038
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0039"
down_revision: str | None = "20260910_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("subcontracts.module.view", "module", "view", "Access work orders and progress claims.", "medium"),
    ("subcontracts.contract.view", "contract", "view", "View work orders and scope lines.", "high"),
    ("subcontracts.contract.create", "contract", "create", "Create draft work orders.", "high"),
    ("subcontracts.contract.manage", "contract", "manage", "Edit work-order scope and lifecycle.", "high"),
    ("subcontracts.contract.submit", "contract", "submit", "Submit work orders for approval.", "high"),
    ("subcontracts.contract.approve", "contract", "approve", "Approve work orders.", "critical"),
    ("subcontracts.contract.issue", "contract", "issue", "Issue approved work orders.", "critical"),
    ("subcontracts.claim.view", "claim", "view", "View subcontractor progress claims.", "high"),
    ("subcontracts.claim.create", "claim", "create", "Create progress claims.", "high"),
    ("subcontracts.claim.manage", "claim", "manage", "Edit draft claim lines.", "high"),
    ("subcontracts.claim.submit", "claim", "submit", "Submit progress claims for certification.", "high"),
    ("subcontracts.claim.certify", "claim", "certify", "Certify or reject progress claims.", "critical"),
    ("subcontracts.claim.payment", "claim", "payment", "Record operational payment state for certified claims.", "critical"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "subcontract_project_counters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("next_contract_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("next_claim_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("next_contract_number >= 1", name="ck_subcontract_counter_contract"),
        sa.CheckConstraint("next_claim_number >= 1", name="ck_subcontract_counter_claim"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_subcontract_counter_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", name="pk_subcontract_project_counters"),
    )
    op.create_index("ix_subcontract_project_counters_organization_id", "subcontract_project_counters", ["organization_id"])

    op.create_table(
        "subcontracts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("contractor_party_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.Enum("draft", "submitted", "approved", "issued", "active", "completed", "cancelled", name="subcontractstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("original_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("retention_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("original_amount >= 0", name="ck_subcontracts_original_amount"),
        sa.CheckConstraint("retention_percent >= 0", name="ck_subcontracts_retention"),
        sa.CheckConstraint("revision >= 1", name="ck_subcontracts_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_subcontracts_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contractor_party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_subcontracts_contractor_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "approved_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_subcontracts_approver_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_subcontracts"),
        sa.UniqueConstraint("project_id", "number", name="uq_subcontracts_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_subcontracts_scope"),
    )
    op.create_index("ix_subcontracts_project_status", "subcontracts", ["project_id", "status"])

    op.create_table(
        "subcontract_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("subcontract_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name="ck_subcontract_lines_quantity"),
        sa.CheckConstraint("rate >= 0", name="ck_subcontract_lines_rate"),
        sa.CheckConstraint("amount >= 0", name="ck_subcontract_lines_amount"),
        sa.ForeignKeyConstraint(["subcontract_id", "project_id", "organization_id"], ["subcontracts.id", "subcontracts.project_id", "subcontracts.organization_id"], name="fk_subcontract_lines_contract_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_subcontract_lines_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["boq_item_id", "project_id", "organization_id"], ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"], name="fk_subcontract_lines_boq_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_subcontract_lines"),
        sa.UniqueConstraint("subcontract_id", "line_number", name="uq_subcontract_line_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_subcontract_lines_scope"),
    )

    op.create_table(
        "subcontract_claims",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("subcontract_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("draft", "submitted", "certified", "rejected", "paid", "cancelled", name="subcontractclaimstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("retention_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("other_deductions", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_withheld_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("certified_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("submitted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certified_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("gross_amount >= 0", name="ck_subcontract_claims_gross"),
        sa.CheckConstraint("retention_amount >= 0", name="ck_subcontract_claims_retention"),
        sa.CheckConstraint("other_deductions >= 0", name="ck_subcontract_claims_deductions"),
        sa.CheckConstraint("tax_withheld_amount >= 0", name="ck_subcontract_claims_tax_withheld"),
        sa.CheckConstraint("certified_amount >= 0", name="ck_subcontract_claims_certified"),
        sa.CheckConstraint("paid_amount >= 0", name="ck_subcontract_claims_paid"),
        sa.CheckConstraint("revision >= 1", name="ck_subcontract_claims_revision"),
        sa.ForeignKeyConstraint(["subcontract_id", "project_id", "organization_id"], ["subcontracts.id", "subcontracts.project_id", "subcontracts.organization_id"], name="fk_subcontract_claims_contract_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "submitted_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_subcontract_claims_submitter_project_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "certified_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_subcontract_claims_certifier_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_subcontract_claims"),
        sa.UniqueConstraint("project_id", "number", name="uq_subcontract_claims_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_subcontract_claims_scope"),
    )
    op.create_index("ix_subcontract_claims_project_status", "subcontract_claims", ["project_id", "status", "period_to"])

    op.create_table(
        "subcontract_claim_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("subcontract_line_id", sa.Uuid(), nullable=False),
        sa.Column("measurement_entry_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("certified_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("certified_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("claimed_quantity >= 0", name="ck_subcontract_claim_lines_claimed_qty"),
        sa.CheckConstraint("certified_quantity >= 0", name="ck_subcontract_claim_lines_certified_qty"),
        sa.CheckConstraint("rate >= 0", name="ck_subcontract_claim_lines_rate"),
        sa.CheckConstraint("gross_amount >= 0", name="ck_subcontract_claim_lines_gross"),
        sa.CheckConstraint("certified_amount >= 0", name="ck_subcontract_claim_lines_certified"),
        sa.ForeignKeyConstraint(["claim_id", "project_id", "organization_id"], ["subcontract_claims.id", "subcontract_claims.project_id", "subcontract_claims.organization_id"], name="fk_subcontract_claim_lines_claim_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subcontract_line_id", "project_id", "organization_id"], ["subcontract_lines.id", "subcontract_lines.project_id", "subcontract_lines.organization_id"], name="fk_subcontract_claim_lines_contract_line_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["measurement_entry_id", "project_id", "organization_id"], ["measurement_entries.id", "measurement_entries.project_id", "measurement_entries.organization_id"], name="fk_subcontract_claim_lines_measurement_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_subcontract_claim_lines"),
        sa.UniqueConstraint("claim_id", "subcontract_line_id", name="uq_subcontract_claim_line"),
    )

    permissions = sa.table("permissions", sa.column("key", sa.String), sa.column("module", sa.String), sa.column("resource", sa.String), sa.column("action", sa.String), sa.column("description", sa.Text), sa.column("risk", sa.String), sa.column("is_active", sa.Boolean))
    op.bulk_insert(permissions, [{"key": key, "module": "subcontracts", "resource": resource, "action": action, "description": description, "risk": risk, "is_active": True} for key, resource, action, description, risk in _PERMISSIONS])


def downgrade() -> None:
    keys = ",".join(f"'{item[0]}'" for item in _PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM permissions WHERE key IN ({keys})"))
    op.drop_table("subcontract_claim_lines")
    op.drop_table("subcontract_claims")
    op.drop_table("subcontract_lines")
    op.drop_table("subcontracts")
    op.drop_table("subcontract_project_counters")
