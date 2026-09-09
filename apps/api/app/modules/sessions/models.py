from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class AuthenticationMethod(StrEnum):
    OIDC = "oidc"
    LOCAL_PASSWORD = "local_password"
    PASSKEY = "passkey"
    RECOVERY = "recovery"


class AuthenticationLevel(StrEnum):
    SINGLE_FACTOR = "single_factor"
    MFA = "mfa"
    PHISHING_RESISTANT = "phishing_resistant"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Session(UUIDTimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "last_seen_at <= idle_expires_at",
            name="ck_sessions_last_seen_before_idle_expiry",
        ),
        CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_sessions_idle_before_absolute_expiry",
        ),
        Index("uq_sessions_token_hash", "token_hash", unique=True),
        Index("ix_sessions_user_active", "user_id", "revoked_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    authentication_method: Mapped[AuthenticationMethod] = mapped_column(
        Enum(AuthenticationMethod, native_enum=False, values_callable=enum_values)
    )
    authentication_level: Mapped[AuthenticationLevel] = mapped_column(
        Enum(AuthenticationLevel, native_enum=False, values_callable=enum_values)
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
