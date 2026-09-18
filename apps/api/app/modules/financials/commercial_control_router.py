from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.commercial_control import build_boq_commercial_control
from app.modules.financials.commercial_control_schemas import BOQCommercialControlSummary
from app.modules.financials.service import FinancialConflictError, FinancialValidationError
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession

router = APIRouter(tags=["financials"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/financials/commercial-control/boq",
    response_model=BOQCommercialControlSummary,
)
async def get_boq_commercial_control(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> BOQCommercialControlSummary:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.project_cost.view")
    try:
        return await build_boq_commercial_control(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
        )
    except FinancialConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FinancialValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
