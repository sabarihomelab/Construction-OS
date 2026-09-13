"""Bind external memberships to the party they represent.

Revision ID: 20260912_0056
Revises: 20260912_0055
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0056"
down_revision: str | None = "20260912_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "membership_party_affiliations",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("party_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_membership_party_affiliation_membership_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_membership_party_affiliation_party_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("membership_id"),
    )
    op.create_index(
        "ix_membership_party_affiliations_organization_id",
        "membership_party_affiliations",
        ["organization_id"],
    )
    op.create_index(
        "ix_membership_party_affiliations_party_id",
        "membership_party_affiliations",
        ["party_id"],
    )
    op.create_index(
        "ix_membership_party_affiliations_org_party",
        "membership_party_affiliations",
        ["organization_id", "party_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_membership_party_affiliations_org_party",
        table_name="membership_party_affiliations",
    )
    op.drop_index(
        "ix_membership_party_affiliations_party_id",
        table_name="membership_party_affiliations",
    )
    op.drop_index(
        "ix_membership_party_affiliations_organization_id",
        table_name="membership_party_affiliations",
    )
    op.drop_table("membership_party_affiliations")
