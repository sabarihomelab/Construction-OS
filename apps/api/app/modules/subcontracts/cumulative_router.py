from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession
from app.modules.subcontracts.cumulative_schemas import SubcontractClaimCumulativeRead
from app.modules.subcontracts.cumulative_service import build_subcontract_claim_cumulative
from app.modules.subcontracts.service import SubcontractValidationError

router = APIRouter(tags=["subcontracts"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/subcontracts/{subcontract_id}/claims/{claim_id}/cumulative",
    response_model=SubcontractClaimCumulativeRead,
)
async def get_subcontract_claim_cumulative(
    project_id: UUID,
    subcontract_id: UUID,
    claim_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> SubcontractClaimCumulativeRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "subcontracts.claim.view")
    try:
        return await build_subcontract_claim_cumulative(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            subcontract_id=subcontract_id,
            claim_id=claim_id,
        )
    except SubcontractValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
