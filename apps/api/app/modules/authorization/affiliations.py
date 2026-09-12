from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.authorization.models import MembershipPartyAffiliation, OrganizationAuthorizationState
from app.modules.commercial.models import Party, PartyStatus
from app.modules.events.service import enqueue_event
from app.modules.identity.models import MembershipKind, OrganizationMembership


class PartyAffiliationValidationError(ValueError):
    pass


async def list_party_references(db: AsyncSession, organization_id: UUID) -> list[Party]:
    rows = await db.scalars(
        select(Party)
        .where(
            Party.organization_id == organization_id,
            Party.status == PartyStatus.ACTIVE,
        )
        .order_by(Party.name, Party.code)
    )
    return list(rows.all())


async def get_membership_party(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
) -> Party | None:
    affiliation = await db.scalar(
        select(MembershipPartyAffiliation).where(
            MembershipPartyAffiliation.membership_id == membership_id,
            MembershipPartyAffiliation.organization_id == organization_id,
        )
    )
    if affiliation is None:
        return None
    return await db.scalar(
        select(Party).where(
            Party.id == affiliation.party_id,
            Party.organization_id == organization_id,
        )
    )


async def set_membership_party(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    party_id: UUID | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> Party | None:
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise PartyAffiliationValidationError("Membership was not found")

    affiliation = await db.scalar(
        select(MembershipPartyAffiliation).where(
            MembershipPartyAffiliation.membership_id == membership_id,
            MembershipPartyAffiliation.organization_id == organization_id,
        )
    )
    before_party_id = affiliation.party_id if affiliation is not None else None

    party: Party | None = None
    if party_id is not None:
        if membership.kind != MembershipKind.EXTERNAL:
            raise PartyAffiliationValidationError(
                "Only external memberships can be linked to a represented party"
            )
        party = await db.scalar(
            select(Party).where(
                Party.id == party_id,
                Party.organization_id == organization_id,
                Party.status == PartyStatus.ACTIVE,
            )
        )
        if party is None:
            raise PartyAffiliationValidationError("Active party was not found")
        if affiliation is None:
            affiliation = MembershipPartyAffiliation(
                membership_id=membership_id,
                organization_id=organization_id,
                party_id=party.id,
            )
            db.add(affiliation)
        else:
            affiliation.party_id = party.id
    elif affiliation is not None:
        await db.delete(affiliation)

    if before_party_id == party_id:
        return party

    state = await db.get(OrganizationAuthorizationState, organization_id)
    if state is None:
        state = OrganizationAuthorizationState(organization_id=organization_id, revision=1)
        db.add(state)
    else:
        state.revision += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="security.membership.party_affiliation.changed",
        target_type="organization_membership",
        target_id=str(membership_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "before_party_id": str(before_party_id) if before_party_id else None,
            "after_party_id": str(party_id) if party_id else None,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="access_context.changed",
        entity_type="organization_membership",
        entity_id=membership_id,
        entity_version=state.revision,
        recipient_membership_id=membership_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"authorization_revision": state.revision},
    )
    return party
