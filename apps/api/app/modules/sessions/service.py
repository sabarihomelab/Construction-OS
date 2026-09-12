import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.identity.models import (
    MembershipStatus,
    OrganizationMembership,
    User,
    UserStatus,
)
from app.modules.sessions.models import AuthenticationLevel, AuthenticationMethod, Session


class SessionValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session: Session
    token: str
    csrf_token: str


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_secret() -> str:
    return secrets.token_urlsafe(48)


def validate_csrf_token(session: Session, raw_csrf_token: str) -> bool:
    return hmac.compare_digest(session.csrf_token_hash, hash_secret(raw_csrf_token))


def _membership_matches_deployment(membership: OrganizationMembership) -> bool:
    deployment_organization_id = get_settings().deployment_organization_id
    return (
        deployment_organization_id is None
        or membership.organization_id == deployment_organization_id
    )


async def create_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    membership_id: UUID,
    authentication_method: AuthenticationMethod,
    authentication_level: AuthenticationLevel,
    mfa_verified_at: datetime | None = None,
    now: datetime | None = None,
) -> IssuedSession:
    settings = get_settings()
    now = now or datetime.now(UTC)

    membership = await db.get(OrganizationMembership, membership_id)
    if (
        membership is None
        or membership.user_id != user_id
        or membership.status != MembershipStatus.ACTIVE
    ):
        raise SessionValidationError("An active membership is required to create a session")
    if not _membership_matches_deployment(membership):
        raise SessionValidationError("Membership does not belong to this deployment")

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.status != UserStatus.ACTIVE:
        raise SessionValidationError("An active user is required to create a session")

    token = generate_secret()
    csrf_token = generate_secret()
    absolute_expires_at = now + timedelta(seconds=settings.session_absolute_timeout_seconds)
    idle_expires_at = min(
        now + timedelta(seconds=settings.session_idle_timeout_seconds),
        absolute_expires_at,
    )

    session = Session(
        user_id=user_id,
        membership_id=membership_id,
        token_hash=hash_secret(token),
        csrf_token_hash=hash_secret(csrf_token),
        authentication_method=authentication_method,
        authentication_level=authentication_level,
        last_seen_at=now,
        idle_expires_at=idle_expires_at,
        absolute_expires_at=absolute_expires_at,
        mfa_verified_at=mfa_verified_at,
    )
    db.add(session)
    await db.flush()
    return IssuedSession(session=session, token=token, csrf_token=csrf_token)


async def load_active_session(
    db: AsyncSession,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> Session:
    settings = get_settings()
    now = now or datetime.now(UTC)
    session = await db.scalar(select(Session).where(Session.token_hash == hash_secret(raw_token)))
    if session is None or session.revoked_at is not None:
        raise SessionValidationError("Session is not active")

    if now >= session.absolute_expires_at:
        await revoke_session(db, session, "absolute_timeout", now=now)
        await db.commit()
        raise SessionValidationError("Session has expired")

    if now >= session.idle_expires_at:
        await revoke_session(db, session, "idle_timeout", now=now)
        await db.commit()
        raise SessionValidationError("Session has expired")

    membership = await db.get(OrganizationMembership, session.membership_id)
    if (
        membership is None
        or membership.user_id != session.user_id
        or membership.status != MembershipStatus.ACTIVE
    ):
        await revoke_session(db, session, "membership_inactive", now=now)
        await db.commit()
        raise SessionValidationError("Session membership is no longer active")
    if not _membership_matches_deployment(membership):
        await revoke_session(db, session, "deployment_mismatch", now=now)
        await db.commit()
        raise SessionValidationError("Session does not belong to this deployment")

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active or user.status != UserStatus.ACTIVE:
        await revoke_session(db, session, "user_inactive", now=now)
        await db.commit()
        raise SessionValidationError("Session user is no longer active")

    touch_after = timedelta(seconds=settings.session_touch_interval_seconds)
    if now - session.last_seen_at >= touch_after:
        session.last_seen_at = now
        session.idle_expires_at = min(
            now + timedelta(seconds=settings.session_idle_timeout_seconds),
            session.absolute_expires_at,
        )
        await db.commit()

    return session


async def revoke_session(
    db: AsyncSession,
    session: Session,
    reason: str,
    *,
    now: datetime | None = None,
) -> None:
    if session.revoked_at is not None:
        return
    session.revoked_at = now or datetime.now(UTC)
    session.revocation_reason = reason[:120]
    await db.flush()


async def revoke_all_user_sessions(
    db: AsyncSession,
    user_id: UUID,
    reason: str,
    *,
    now: datetime | None = None,
) -> int:
    revoked_at = now or datetime.now(UTC)
    result = await db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=revoked_at, revocation_reason=reason[:120])
    )
    return result.rowcount or 0
