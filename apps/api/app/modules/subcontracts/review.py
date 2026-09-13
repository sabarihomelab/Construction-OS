from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.search.service import schedule_search_index
from app.modules.subcontracts.models import SubcontractClaim, SubcontractClaimStatus
from app.modules.subcontracts.service import SubcontractConflictError, SubcontractValidationError


async def reject_claim(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    claim = await db.scalar(
        select(SubcontractClaim)
        .where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.organization_id == organization_id,
        )
        .with_for_update()
    )
    if claim is None:
        raise SubcontractValidationError("Progress claim was not found")
    if claim.revision != expected_revision:
        raise SubcontractConflictError("Progress claim changed; refresh before rejecting")
    if claim.status != SubcontractClaimStatus.SUBMITTED:
        raise SubcontractValidationError("Only submitted claims can be rejected")
    claim.status = SubcontractClaimStatus.REJECTED
    claim.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.claim.rejected",
        target_type="subcontract_claim",
        target_id=str(claim.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": claim.status.value, "revision": claim.revision},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="subcontracts.claim.rejected",
        entity_type="subcontract_claim",
        entity_id=claim.id,
        entity_version=claim.revision,
        required_permission_key="subcontracts.claim.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": claim.revision},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="subcontract_claim",
        entity_id=claim.id,
        entity_version=claim.revision,
    )
    return claim
