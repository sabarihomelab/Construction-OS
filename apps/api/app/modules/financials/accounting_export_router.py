from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.accounting_export_schemas import (
    AccountingCostRegisterExport,
    TallyPrimeExportPreview,
)
from app.modules.financials.accounting_export_service import (
    build_cost_register_export,
    build_tallyprime_preview,
    serialize_cost_register_csv,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
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


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, FinancialConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/financials/accounting-export/cost-register",
    response_model=AccountingCostRegisterExport,
)
async def preview_cost_register_export(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> AccountingCostRegisterExport:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.accounting_export.view")
    try:
        return await build_cost_register_export(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/financials/accounting-export/cost-register.csv",
    response_class=Response,
)
async def download_cost_register_csv(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.accounting_export.export")
    try:
        export = await build_cost_register_export(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        _domain_error(exc)

    if not export.ready_for_export:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Accounting export has unmapped Cost Heads; complete ledger mapping before export"
            ),
        )

    filename = f"project-{project_id}-cost-register.csv"
    return Response(
        content=serialize_cost_register_csv(export),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/projects/{project_id}/financials/accounting-export/tallyprime-preview",
    response_model=TallyPrimeExportPreview,
)
async def preview_tallyprime_export(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> TallyPrimeExportPreview:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.accounting_export.export")
    try:
        return await build_tallyprime_preview(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        _domain_error(exc)
