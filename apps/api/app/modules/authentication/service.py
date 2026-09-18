from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authentication.providers import AuthenticationAssertion
from app.modules.identity.models import OrganizationMembership, User, UserStatus
from app.modules.sessions.service import IssuedSession, create_session


class AuthenticationValidationError(ValueError):
    pass


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or "@" not in normalized:
        raise AuthenticationValidationError("Authentication assertion email is invalid")
    return normalized


def validate_assertion(assertion: AuthenticationAssertion, *, now: datetime | None = None) -> None:
    current = now or datetime.now(UTC)
    if not assertion.provider_key.strip() or not assertion.subject.strip():
        raise AuthenticationValidationError("Authentication provider and subject are required")
    _normalize_email(assertion.email)
    if assertion.authenticated_at.tzinfo is None:
        raise AuthenticationValidationError("Authentication timestamp must be timezone-aware")
    if assertion.authenticated_at > current:
        raise AuthenticationValidationError("Authentication assertion timestamp is in the future")
    if assertion.mfa_verified_at is not None and assertion.mfa_verified_at.tzinfo is None:
        raise AuthenticationValidationError("MFA timestamp must be timezone-aware")


async def bind_verified_identity(
    db: AsyncSession,
    *,
    user_id: UUID,
    assertion: AuthenticationAssertion,
) -> User:
    validate_assertion(assertion)
    if not assertion.email_verified:
        raise AuthenticationValidationError("Verified email is required to bind an identity")

    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or not user.is_active or user.status != UserStatus.ACTIVE:
        raise AuthenticationValidationError("Active user was not found")
    if _normalize_email(user.primary_email) != _normalize_email(assertion.email):
        raise AuthenticationValidationError("Verified identity email does not match the user")

    existing = await db.scalar(
        select(User).where(
            User.identity_provider == assertion.provider_key,
            User.identity_subject == assertion.subject,
            User.id != user.id,
        )
    )
    if existing is not None:
        raise AuthenticationValidationError("Identity is already bound to another user")
    if user.identity_provider is not None or user.identity_subject is not None:
        if (
            user.identity_provider != assertion.provider_key
            or user.identity_subject != assertion.subject
        ):
            raise AuthenticationValidationError("User already has a different bound identity")
        return user

    user.identity_provider = assertion.provider_key
    user.identity_subject = assertion.subject
    user.last_authenticated_at = assertion.authenticated_at
    await db.flush()
    return user


async def issue_session_for_assertion(
    db: AsyncSession,
    *,
    assertion: AuthenticationAssertion,
    membership_id: UUID,
) -> IssuedSession:
    validate_assertion(assertion)
    user = await db.scalar(
        select(User).where(
            User.identity_provider == assertion.provider_key,
            User.identity_subject == assertion.subject,
            User.is_active.is_(True),
            User.status == UserStatus.ACTIVE,
        )
    )
    if user is None:
        raise AuthenticationValidationError("Authenticated identity is not linked to an active user")

    membership = await db.get(OrganizationMembership, membership_id)
    if membership is None or membership.user_id != user.id:
        raise AuthenticationValidationError("Membership does not belong to the authenticated user")

    user.last_authenticated_at = assertion.authenticated_at
    await db.flush()
    return await create_session(
        db,
        user_id=user.id,
        membership_id=membership.id,
        authentication_method=assertion.method,
        authentication_level=assertion.level,
        mfa_verified_at=assertion.mfa_verified_at,
    )
