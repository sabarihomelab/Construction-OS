from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.files.generated import GeneratedFileError, store_generated_file
from app.modules.files.service import FileValidationError, link_file_asset
from app.modules.financials.accounting_export_schemas import (
    AccountingCostRegisterExport,
    AccountingGeneratedFileRead,
    TallyPrimeExportPreview,
)
from app.modules.financials.accounting_export_service import (
    build_cost_register_export,
    build_tallyprime_preview,
    serialize_cost_register_csv,
    serialize_cost_register_xlsx,
    serialize_tallyprime_xml,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

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



async def _store_accounting_export(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    actor_user_id: UUID,
    filename: str,
    content: bytes,
    content_type: str,
    adapter: str,
    from_date: date | None,
    to_date: date | None,
) -> AccountingGeneratedFileRead:
    asset, version = await store_generated_file(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        filename=filename,
        content=content,
        content_type=content_type,
        source_system="financials.accounting_export",
        source_metadata={
            "project_id": str(project_id),
            "adapter": adapter,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
        },
    )
    await link_file_asset(
        db,
        organization_id=organization_id,
        entity_type="project",
        entity_id=project_id,
        asset_id=asset.id,
        relation_type="accounting_export",
        pinned_version=version.version,
        actor_user_id=actor_user_id,
    )
    return AccountingGeneratedFileRead(
        asset_id=asset.id,
        version=version.version,
        filename=version.original_filename,
        content_type=version.detected_content_type or content_type,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
    )


@router.post(
    "/projects/{project_id}/financials/accounting-export/cost-register.xlsx",
    response_model=AccountingGeneratedFileRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_cost_register_xlsx(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
    from_date: date | None = None,
    to_date: date | None = None,
) -> AccountingGeneratedFileRead:
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
        result = await _store_accounting_export(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            filename=f"project-{project_id}-cost-register.xlsx",
            content=serialize_cost_register_xlsx(export),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            adapter="cost_register_xlsx",
            from_date=from_date,
            to_date=to_date,
        )
        await db.commit()
        return result
    except (
        FinancialConflictError,
        FinancialValidationError,
        GeneratedFileError,
        FileValidationError,
    ) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/financials/accounting-export/tallyprime.xml",
    response_model=AccountingGeneratedFileRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_tallyprime_xml(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
    from_date: date | None = None,
    to_date: date | None = None,
) -> AccountingGeneratedFileRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.accounting_export.export")
    try:
        preview = await build_tallyprime_preview(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
        )
        result = await _store_accounting_export(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            filename=f"project-{project_id}-tallyprime.xml",
            content=serialize_tallyprime_xml(preview),
            content_type="application/xml",
            adapter="tallyprime_xml_v1",
            from_date=from_date,
            to_date=to_date,
        )
        await db.commit()
        return result
    except (
        FinancialConflictError,
        FinancialValidationError,
        GeneratedFileError,
        FileValidationError,
    ) as exc:
        await db.rollback()
        _domain_error(exc)
