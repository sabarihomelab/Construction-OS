"""Create short-lived native authentication grants.

Revision ID: 20260911_0054
Revises: 20260911_0053
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0054"
down_revision: str | None = "20260911_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mobile_authentication_grants",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("grant_token_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "authentication_method",
            sa.Enum(
                "oidc",
                "local_password",
                "passkey",
                "recovery",
                name="authenticationmethod",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "authentication_level",
            sa.Enum(
                "single_factor",
                "mfa",
                "phishing_resistant",
                name="authenticationlevel",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mobile_authentication_grants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mobile_authentication_grants")),
    )
    op.create_index(
        op.f("ix_mobile_authentication_grants_user_id"),
        "mobile_authentication_grants",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobile_authentication_grants_expires_at"),
        "mobile_authentication_grants",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "uq_mobile_authentication_grants_token_hash",
        "mobile_authentication_grants",
        ["grant_token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_mobile_authentication_grants_user_active",
        "mobile_authentication_grants",
        ["user_id", "consumed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mobile_authentication_grants_user_active",
        table_name="mobile_authentication_grants",
    )
    op.drop_index(
        "uq_mobile_authentication_grants_token_hash",
        table_name="mobile_authentication_grants",
    )
    op.drop_index(
        op.f("ix_mobile_authentication_grants_expires_at"),
        table_name="mobile_authentication_grants",
    )
    op.drop_index(
        op.f("ix_mobile_authentication_grants_user_id"),
        table_name="mobile_authentication_grants",
    )
    op.drop_table("mobile_authentication_grants")
