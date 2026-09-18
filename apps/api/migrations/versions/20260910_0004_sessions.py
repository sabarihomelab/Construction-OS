"""Create opaque server sessions.

Revision ID: 20260910_0004
Revises: 20260910_0003
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0004"
down_revision: str | None = "20260910_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
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
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=120), nullable=True),
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
        sa.CheckConstraint(
            "last_seen_at <= idle_expires_at",
            name="ck_sessions_last_seen_before_idle_expiry",
        ),
        sa.CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_sessions_idle_before_absolute_expiry",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["organization_memberships.id"],
            name=op.f("fk_sessions_membership_id_organization_memberships"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_sessions_membership_id"), "sessions", ["membership_id"], unique=False
    )
    op.create_index(
        op.f("ix_sessions_idle_expires_at"), "sessions", ["idle_expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_sessions_absolute_expires_at"),
        "sessions",
        ["absolute_expires_at"],
        unique=False,
    )
    op.create_index("uq_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index(
        "ix_sessions_user_active", "sessions", ["user_id", "revoked_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_index("uq_sessions_token_hash", table_name="sessions")
    op.drop_index(op.f("ix_sessions_absolute_expires_at"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_idle_expires_at"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_membership_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
