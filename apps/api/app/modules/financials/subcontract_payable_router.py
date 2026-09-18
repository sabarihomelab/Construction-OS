from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.subcontract_payable_schemas import SubcontractPayableRead
from app.modules.financials.subcontract_payable_service import (
    SubcontractPayableProjectionError,
    get_subcontract_payable,
    list_subcontract_payables,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession

router = APIRouter(tags=["financials"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={
            key: set(values) for key, values in context.project_permissions.items()
        },
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/financials/payables/subcontract-claims",
    response_model=list[SubcontractPayableRead],
)
async def list_subcontract_payables_route(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SubcontractPayableRead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.view")
    return await list_subcontract_payables(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
    )


@router.get(
    "/projects/{project_id}/financials/payables/subcontract-claims/{claim_id}",
    response_model=SubcontractPayableRead,
)
async def get_subcontract_payable_route(
    project_id: UUID,
    claim_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> SubcontractPayableRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.view")
    try:
        return await get_subcontract_payable(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            claim_id=claim_id,
        )
    except SubcontractPayableProjectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
