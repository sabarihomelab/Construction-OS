from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field.dpr_custom_field_schemas import (
    DPRCustomFieldDefinitionsRead,
    DPRCustomFieldReplace,
    DPRCustomFieldValuesRead,
)
from app.modules.field.dpr_custom_field_service import (
    list_dpr_custom_field_definitions,
    list_dpr_custom_field_values,
    replace_dpr_custom_fields,
)
from app.modules.field.dpr_service import DPRConflictError, DPRValidationError
from app.modules.field.router import _require_permission
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["daily-progress-report-custom-fields"])


def _permission_keys(context, project_id: UUID) -> set[str]:
    result = set(context.permissions)
    result.update(context.project_permissions.get(str(project_id), []))
    return result


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, DPRConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/daily-reports/custom-fields/definitions",
    response_model=DPRCustomFieldDefinitionsRead,
)
async def get_dpr_custom_field_definitions(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DPRCustomFieldDefinitionsRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    fields = await list_dpr_custom_field_definitions(
        db,
        organization_id=context.organization_id,
        permission_keys=_permission_keys(context, project_id),
    )
    return DPRCustomFieldDefinitionsRead(project_id=project_id, fields=fields)


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/custom-fields",
    response_model=DPRCustomFieldValuesRead,
)
async def get_dpr_custom_field_values(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DPRCustomFieldValuesRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    try:
        return await list_dpr_custom_field_values(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            permission_keys=_permission_keys(context, project_id),
        )
    except DPRValidationError as exc:
        _domain_error(exc)


@router.put(
    "/projects/{project_id}/daily-reports/{report_id}/custom-fields",
    response_model=DPRCustomFieldValuesRead,
)
async def put_dpr_custom_field_values(
    project_id: UUID,
    report_id: UUID,
    payload: DPRCustomFieldReplace,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DPRCustomFieldValuesRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    permissions = _permission_keys(context, project_id)
    try:
        report = await replace_dpr_custom_fields(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            values=payload.values,
            permission_keys=permissions,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return await list_dpr_custom_field_values(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report.id,
            permission_keys=permissions,
        )
    except (DPRConflictError, DPRValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
