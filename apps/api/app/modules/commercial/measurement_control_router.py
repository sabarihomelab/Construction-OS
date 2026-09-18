from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.commercial.measurement_control import build_boq_measurement_control
from app.modules.commercial.measurement_control_schemas import BOQMeasurementControlSummary
from app.modules.commercial.service import CommercialValidationError
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession

router = APIRouter(tags=["commercial"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/commercial/measurement-control/boq",
    response_model=BOQMeasurementControlSummary,
)
async def get_boq_measurement_control(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> BOQMeasurementControlSummary:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.measurement.view")
    try:
        return await build_boq_measurement_control(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
        )
    except CommercialValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
