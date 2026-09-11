from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field import dpr_provider  # noqa: F401
from app.modules.field.dpr_provider import DPR_REPORT_TYPE_KEY
from app.modules.field.dpr_schemas import (
    DPRRenderRequest,
    DPRReportPayloadRead,
    DPRWorkProgressRead,
    DPRWorkProgressReplace,
)
from app.modules.field.dpr_service import (
    DPRConflictError,
    DPRValidationError,
    list_work_progress,
    replace_work_progress,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.reporting.template_api_schemas import (
    ReportBrandingRead,
    ReportBrandingUpdate,
    ReportProviderContractRead,
    ReportRenderRecordRead,
    ReportTemplateRead,
    ReportTemplateVersionRead,
)
from app.modules.reporting.template_provider import report_data_providers
from app.modules.reporting.template_schemas import (
    ReportTemplateCreate,
    ReportTemplatePublish,
    ReportTemplateVersionCreate,
)
from app.modules.reporting.template_service import (
    ReportTemplateConflictError,
    ReportTemplateValidationError,
    build_report_payload,
    create_template,
    create_template_version,
    get_branding,
    list_render_history,
    list_template_versions,
    list_templates,
    publish_template_version,
    render_report_instance,
    update_branding,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["daily-progress-reports"])


def _require_permission(context, project_id: UUID, permission_key: str) -> None:
    project_permissions = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, (DPRConflictError, ReportTemplateConflictError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/work-progress",
    response_model=list[DPRWorkProgressRead],
)
async def get_work_progress(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    return await list_work_progress(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_id=report_id,
    )


@router.put(
    "/projects/{project_id}/daily-reports/{report_id}/work-progress",
    response_model=list[DPRWorkProgressRead],
)
async def put_work_progress(
    project_id: UUID,
    report_id: UUID,
    payload: DPRWorkProgressReplace,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    try:
        await replace_work_progress(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            rows=payload.rows,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        return await list_work_progress(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
        )
    except (DPRConflictError, DPRValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/report-payload",
    response_model=DPRReportPayloadRead,
)
async def get_report_payload(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DPRReportPayloadRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    payload = await build_report_payload(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_type_key=DPR_REPORT_TYPE_KEY,
        source_entity_id=report_id,
    )
    return DPRReportPayloadRead(report_id=report_id, payload=payload)


@router.get(
    "/projects/{project_id}/dpr-templates/contract",
    response_model=ReportProviderContractRead,
)
async def get_dpr_contract(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> ReportProviderContractRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.template.view")
    contract = report_data_providers.get(DPR_REPORT_TYPE_KEY).contract
    return ReportProviderContractRead(
        key=contract.key,
        version=contract.version,
        scalar_paths=list(contract.scalar_paths),
        collections=[{"key": item.key, "fields": list(item.fields)} for item in contract.collections],
        dynamic_prefixes=list(contract.dynamic_prefixes),
        required_permission_key=contract.required_permission_key,
    )


@router.get(
    "/projects/{project_id}/dpr-templates",
    response_model=list[ReportTemplateRead],
)
async def get_templates(project_id: UUID, db: DbSession, session: CurrentSession):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.template.view")
    return await list_templates(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_type_key=DPR_REPORT_TYPE_KEY,
    )


@router.post(
    "/projects/{project_id}/dpr-templates",
    response_model=ReportTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_template(
    project_id: UUID,
    payload: ReportTemplateCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.template.manage")
    try:
        row = await create_template(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_type_key=DPR_REPORT_TYPE_KEY,
            payload=payload,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except ReportTemplateValidationError as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/dpr-templates/{template_id}/versions",
    response_model=list[ReportTemplateVersionRead],
)
async def get_template_versions(
    project_id: UUID,
    template_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.template.view")
    return await list_template_versions(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_type_key=DPR_REPORT_TYPE_KEY,
        template_id=template_id,
    )


@router.post(
    "/projects/{project_id}/dpr-templates/{template_id}/versions",
    response_model=ReportTemplateVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_template_version(
    project_id: UUID,
    template_id: UUID,
    payload: ReportTemplateVersionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.template.manage")
    try:
        row = await create_template_version(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_type_key=DPR_REPORT_TYPE_KEY,
            template_id=template_id,
            payload=payload,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ReportTemplateValidationError, ReportTemplateConflictError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/dpr-templates/{template_id}/versions/{version_id}/publish",
    response_model=ReportTemplateVersionRead,
)
async def publish_version(
    project_id: UUID,
    template_id: UUID,
    version_id: UUID,
    payload: ReportTemplatePublish,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.template.manage")
    try:
        row = await publish_template_version(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_type_key=DPR_REPORT_TYPE_KEY,
            template_id=template_id,
            version_id=version_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ReportTemplateValidationError, ReportTemplateConflictError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/daily-reports/{report_id}/render")
async def render_dpr(
    project_id: UUID,
    report_id: UUID,
    payload: DPRRenderRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.dpr.render")
    try:
        content, content_type, filename, _version, _record = await render_report_instance(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_type_key=DPR_REPORT_TYPE_KEY,
            source_entity_id=report_id,
            actor_user_id=session.user_id,
            output_format=payload.output_format,
            template_version_id=payload.template_version_id,
            persist_history=payload.persist_history,
        )
        if payload.persist_history:
            await db.commit()
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except (ReportTemplateValidationError, ValueError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/render-history",
    response_model=list[ReportRenderRecordRead],
)
async def get_render_history(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    return await list_render_history(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_type_key=DPR_REPORT_TYPE_KEY,
        source_entity_id=report_id,
    )


@router.get("/dpr-branding", response_model=ReportBrandingRead | None)
async def get_dpr_branding(db: DbSession, session: CurrentSession):
    context = await build_access_context(db, session.membership_id)
    if "field.dpr.template.view" not in set(context.permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return await get_branding(db, organization_id=context.organization_id)


@router.put("/dpr-branding", response_model=ReportBrandingRead)
async def put_dpr_branding(
    payload: ReportBrandingUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    if "field.dpr.template.manage" not in set(context.permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    try:
        row = await update_branding(
            db,
            organization_id=context.organization_id,
            payload=payload,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ReportTemplateValidationError, ReportTemplateConflictError) as exc:
        await db.rollback()
        _domain_error(exc)
