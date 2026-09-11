from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authentication.providers import AuthenticationAssertion
from app.modules.identity.models import MembershipStatus, OrganizationMembership, User, UserStatus
from app.modules.organizations.models import Organization
from app.modules.sessions.models import MobileAuthenticationGrant
from app.modules.sessions.service import (
    IssuedSession,
    create_session,
    generate_secret,
    hash_secret,
)


class NativeAuthenticationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MembershipOption:
    membership_id: UUID
    organization_id: UUID
    organization_name: str


@dataclass(frozen=True, slots=True)
class PendingMembershipSelection:
    grant_token: str
    memberships: tuple[MembershipOption, ...]


def _assertion_from_grant(grant: MobileAuthenticationGrant) -> AuthenticationAssertion:
    return AuthenticationAssertion(
        provider_key=grant.provider_key,
        subject=grant.subject,
        email=grant.email,
        email_verified=grant.email_verified,
        display_name=grant.display_name,
        method=grant.authentication_method,
        level=grant.authentication_level,
        authenticated_at=grant.authenticated_at,
        mfa_verified_at=grant.mfa_verified_at,
    )


async def _active_user_for_assertion(
    db: AsyncSession,
    assertion: AuthenticationAssertion,
    *,
    allow_verified_email_lookup: bool = False,
) -> tuple[User, bool]:
    user = await db.scalar(
        select(User).where(
            User.identity_provider == assertion.provider_key,
            User.identity_subject == assertion.subject,
            User.is_active.is_(True),
            User.status == UserStatus.ACTIVE,
        )
    )
    if user is not None:
        return user, True

    if allow_verified_email_lookup and assertion.email_verified:
        normalized_email = assertion.email.strip().lower()
        user = await db.scalar(
            select(User).where(
                func.lower(User.primary_email) == normalized_email,
                User.is_active.is_(True),
                User.status == UserStatus.ACTIVE,
            )
        )
        if user is not None:
            return user, False

    raise NativeAuthenticationError("Authenticated identity is not linked to an active user")


async def active_memberships_for_user(
    db: AsyncSession,
    user_id: UUID,
) -> tuple[MembershipOption, ...]:
    rows = (
        await db.execute(
            select(OrganizationMembership, Organization)
            .join(Organization, Organization.id == OrganizationMembership.organization_id)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
                Organization.is_active.is_(True),
            )
            .order_by(Organization.name, OrganizationMembership.id)
        )
    ).all()
    return tuple(
        MembershipOption(
            membership_id=membership.id,
            organization_id=organization.id,
            organization_name=organization.name,
        )
        for membership, organization in rows
    )


async def begin_native_authentication(
    db: AsyncSession,
    assertion: AuthenticationAssertion,
    *,
    now: datetime | None = None,
    grant_ttl_seconds: int = 300,
    allow_verified_email_lookup: bool = False,
) -> IssuedSession | PendingMembershipSelection:
    from app.modules.authentication.service import issue_session_for_assertion, validate_assertion

    current = now or datetime.now(UTC)
    validate_assertion(assertion, now=current)
    user, identity_linked = await _active_user_for_assertion(
        db,
        assertion,
        allow_verified_email_lookup=allow_verified_email_lookup,
    )
    memberships = await active_memberships_for_user(db, user.id)
    if not memberships:
        raise NativeAuthenticationError("Authenticated user has no active organization membership")
    if len(memberships) == 1:
        if identity_linked:
            return await issue_session_for_assertion(
                db,
                assertion=assertion,
                membership_id=memberships[0].membership_id,
            )
        return await create_session(
            db,
            user_id=user.id,
            membership_id=memberships[0].membership_id,
            authentication_method=assertion.method,
            authentication_level=assertion.level,
            mfa_verified_at=assertion.mfa_verified_at,
        )

    raw_grant = generate_secret()
    grant = MobileAuthenticationGrant(
        user_id=user.id,
        grant_token_hash=hash_secret(raw_grant),
        provider_key=assertion.provider_key,
        subject=assertion.subject,
        email=assertion.email,
        email_verified=assertion.email_verified,
        display_name=assertion.display_name,
        authentication_method=assertion.method,
        authentication_level=assertion.level,
        authenticated_at=assertion.authenticated_at,
        mfa_verified_at=assertion.mfa_verified_at,
        expires_at=current + timedelta(seconds=grant_ttl_seconds),
    )
    db.add(grant)
    await db.flush()
    return PendingMembershipSelection(grant_token=raw_grant, memberships=memberships)


async def complete_native_membership_selection(
    db: AsyncSession,
    *,
    raw_grant_token: str,
    membership_id: UUID,
    now: datetime | None = None,
) -> IssuedSession:
    current = now or datetime.now(UTC)
    grant = await db.scalar(
        select(MobileAuthenticationGrant)
        .where(MobileAuthenticationGrant.grant_token_hash == hash_secret(raw_grant_token))
        .with_for_update()
    )
    if grant is None or grant.consumed_at is not None or current >= grant.expires_at:
        raise NativeAuthenticationError("Authentication grant is invalid or expired")

    membership = await db.get(OrganizationMembership, membership_id)
    if (
        membership is None
        or membership.user_id != grant.user_id
        or membership.status != MembershipStatus.ACTIVE
    ):
        raise NativeAuthenticationError("Selected membership is not available for this user")
    organization = await db.get(Organization, membership.organization_id)
    if organization is None or not organization.is_active:
        raise NativeAuthenticationError("Selected organization is not active")

    grant.consumed_at = current
    await db.flush()
    return await create_session(
        db,
        user_id=grant.user_id,
        membership_id=membership.id,
        authentication_method=grant.authentication_method,
        authentication_level=grant.authentication_level,
        mfa_verified_at=grant.mfa_verified_at,
    )
