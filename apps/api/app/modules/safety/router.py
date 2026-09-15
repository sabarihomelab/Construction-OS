from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.safety.models import (
    InspectionResult,
    InspectionRun,
    InspectionTemplate,
    InspectionTemplateVersion,
    PunchItem,
    SafetyCorrectiveAction,
    SafetyRecord,
)
from app.modules.safety.schemas import (
    CorrectiveActionCreate,
    CorrectiveActionRead,
    CorrectiveActionUpdate,
    InspectionResultsWrite,
    InspectionRunCreate,
    InspectionRunDetailRead,
    InspectionRunRead,
    InspectionTemplateCreate,
    InspectionTemplateRead,
    InspectionTemplateVersionCreate,
    InspectionTemplateVersionRead,
    InspectionTemplateVersionUpdate,
    PunchItemCreate,
    PunchItemRead,
    PunchItemUpdate,
    RejectAction,
    SafetyRecordCreate,
    SafetyRecordRead,
    SafetyRecordUpdate,
    VersionAction,
)
from app.modules.safety.service import (
    SafetyConflictError,
    SafetyValidationError,
    add_corrective_action,
    close_punch_item,
    close_safety_record,
    create_inspection_run,
    create_inspection_template,
    create_inspection_template_version,
    create_punch_item,
    create_safety_record,
    publish_inspection_template_version,
    replace_inspection_results,
    review_inspection,
    submit_inspection,
    update_corrective_action,
    update_inspection_template_version,
    update_punch_item,
    update_safety_record,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["safety"])


def _project_permissions(context, project_id: UUID, permission_key: str) -> set[str]:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return set(context.permissions) | scoped.get(str(project_id), set())


def _org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, SafetyConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/safety/inspection-templates", response_model=list[InspectionTemplateRead])
async def list_inspection_templates(db: DbSession, session: CurrentSession) -> list[InspectionTemplate]:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "safety.inspection.manage")
    rows = await db.scalars(
        select(InspectionTemplate)
        .where(InspectionTemplate.organization_id == context.organization_id)
        .order_by(InspectionTemplate.name, InspectionTemplate.key)
    )
    return list(rows.all())


@router.post(
    "/safety/inspection-templates",
    response_model=InspectionTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_inspection_template_route(
    payload: InspectionTemplateCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionTemplate:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "safety.inspection.manage")
    try:
        template = await create_inspection_template(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(template)
        return template
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/safety/inspection-templates/{template_id}/versions",
    response_model=InspectionTemplateVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_inspection_template_version_route(
    template_id: UUID,
    payload: InspectionTemplateVersionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionTemplateVersion:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "safety.inspection.manage")
    try:
        version = await create_inspection_template_version(
            db,
            organization_id=context.organization_id,
            template_id=template_id,
            checklist=[item.model_dump() for item in payload.checklist],
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(version)
        return version
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.put(
    "/safety/inspection-template-versions/{version_id}",
    response_model=InspectionTemplateVersionRead,
)
async def update_inspection_template_version_route(
    version_id: UUID,
    payload: InspectionTemplateVersionUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionTemplateVersion:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "safety.inspection.manage")
    try:
        version = await update_inspection_template_version(
            db,
            organization_id=context.organization_id,
            version_id=version_id,
            expected_revision=payload.expected_revision,
            checklist=[item.model_dump() for item in payload.checklist],
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(version)
        return version
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/safety/inspection-template-versions/{version_id}/publish",
    response_model=InspectionTemplateVersionRead,
)
async def publish_inspection_template_version_route(
    version_id: UUID,
    payload: VersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionTemplateVersion:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "safety.inspection.manage")
    try:
        version = await publish_inspection_template_version(
            db,
            organization_id=context.organization_id,
            version_id=version_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(version)
        return version
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/safety/records", response_model=list[SafetyRecordRead])
async def list_safety_records(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SafetyRecord]:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.view")
    rows = await db.scalars(
        select(SafetyRecord)
        .where(
            SafetyRecord.organization_id == context.organization_id,
            SafetyRecord.project_id == project_id,
        )
        .order_by(SafetyRecord.number.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/safety/records",
    response_model=SafetyRecordRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_safety_record_route(
    project_id: UUID,
    payload: SafetyRecordCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SafetyRecord:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.create")
    try:
        record = await create_safety_record(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(record)
        return record
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/projects/{project_id}/safety/records/{record_id}", response_model=SafetyRecordRead)
async def update_safety_record_route(
    project_id: UUID,
    record_id: UUID,
    payload: SafetyRecordUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SafetyRecord:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.update")
    try:
        record = await update_safety_record(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            record_id=record_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(record)
        return record
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/safety/records/{record_id}/corrective-actions",
    response_model=list[CorrectiveActionRead],
)
async def list_corrective_actions(
    project_id: UUID,
    record_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SafetyCorrectiveAction]:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.view")
    rows = await db.scalars(
        select(SafetyCorrectiveAction)
        .where(
            SafetyCorrectiveAction.organization_id == context.organization_id,
            SafetyCorrectiveAction.project_id == project_id,
            SafetyCorrectiveAction.safety_record_id == record_id,
        )
        .order_by(SafetyCorrectiveAction.sequence)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/safety/records/{record_id}/corrective-actions",
    response_model=CorrectiveActionRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_corrective_action_route(
    project_id: UUID,
    record_id: UUID,
    payload: CorrectiveActionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SafetyCorrectiveAction:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.update")
    try:
        action = await add_corrective_action(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            record_id=record_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(action)
        return action
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/safety/corrective-actions/{action_id}",
    response_model=CorrectiveActionRead,
)
async def update_corrective_action_route(
    project_id: UUID,
    action_id: UUID,
    payload: CorrectiveActionUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SafetyCorrectiveAction:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.update")
    try:
        action = await update_corrective_action(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            action_id=action_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(action)
        return action
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/safety/records/{record_id}/close",
    response_model=SafetyRecordRead,
)
async def close_safety_record_route(
    project_id: UUID,
    record_id: UUID,
    payload: VersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SafetyRecord:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.record.close")
    try:
        record = await close_safety_record(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            record_id=record_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(record)
        return record
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/inspections", response_model=list[InspectionRunRead])
async def list_inspections(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[InspectionRun]:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.inspection.view")
    rows = await db.scalars(
        select(InspectionRun)
        .where(
            InspectionRun.organization_id == context.organization_id,
            InspectionRun.project_id == project_id,
        )
        .order_by(InspectionRun.number.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/inspections",
    response_model=InspectionRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_inspection_route(
    project_id: UUID,
    payload: InspectionRunCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionRun:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.inspection.create")
    try:
        run = await create_inspection_run(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(run)
        return run
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


async def _inspection_detail(db: DbSession, run: InspectionRun) -> InspectionRunDetailRead:
    rows = await db.scalars(
        select(InspectionResult)
        .where(
            InspectionResult.organization_id == run.organization_id,
            InspectionResult.inspection_run_id == run.id,
        )
        .order_by(InspectionResult.created_at, InspectionResult.item_key)
    )
    from app.modules.safety.schemas import InspectionResultRead

    return InspectionRunDetailRead(
        **InspectionRunRead.model_validate(run).model_dump(),
        results=[InspectionResultRead.model_validate(item) for item in rows.all()],
    )


@router.get(
    "/projects/{project_id}/inspections/{run_id}",
    response_model=InspectionRunDetailRead,
)
async def get_inspection(
    project_id: UUID,
    run_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> InspectionRunDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.inspection.view")
    run = await db.scalar(
        select(InspectionRun).where(
            InspectionRun.id == run_id,
            InspectionRun.organization_id == context.organization_id,
            InspectionRun.project_id == project_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    return await _inspection_detail(db, run)


@router.put(
    "/projects/{project_id}/inspections/{run_id}/results",
    response_model=InspectionRunDetailRead,
)
async def replace_inspection_results_route(
    project_id: UUID,
    run_id: UUID,
    payload: InspectionResultsWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionRunDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.inspection.execute")
    try:
        run = await replace_inspection_results(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            run_id=run_id,
            expected_revision=payload.expected_revision,
            results=[item.model_dump() for item in payload.results],
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(run)
        return await _inspection_detail(db, run)
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/inspections/{run_id}/submit",
    response_model=InspectionRunRead,
)
async def submit_inspection_route(
    project_id: UUID,
    run_id: UUID,
    payload: VersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionRun:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.inspection.execute")
    try:
        run = await submit_inspection(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            run_id=run_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(run)
        return run
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


async def _review_inspection_route(
    *,
    project_id: UUID,
    run_id: UUID,
    payload: VersionAction,
    approve: bool,
    db: DbSession,
    session: CurrentSession,
) -> InspectionRun:
    context = await build_access_context(db, session.membership_id)
    permissions = _project_permissions(context, project_id, "safety.inspection.review")
    try:
        run = await review_inspection(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            run_id=run_id,
            expected_revision=payload.expected_revision,
            approve=approve,
            permission_keys=permissions,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(run)
        return run
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/inspections/{run_id}/approve",
    response_model=InspectionRunRead,
)
async def approve_inspection_route(
    project_id: UUID,
    run_id: UUID,
    payload: VersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionRun:
    return await _review_inspection_route(
        project_id=project_id,
        run_id=run_id,
        payload=payload,
        approve=True,
        db=db,
        session=session,
    )


@router.post(
    "/projects/{project_id}/inspections/{run_id}/reject",
    response_model=InspectionRunRead,
)
async def reject_inspection_route(
    project_id: UUID,
    run_id: UUID,
    payload: RejectAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> InspectionRun:
    return await _review_inspection_route(
        project_id=project_id,
        run_id=run_id,
        payload=payload,
        approve=False,
        db=db,
        session=session,
    )


@router.get("/projects/{project_id}/punch", response_model=list[PunchItemRead])
async def list_punch_items(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[PunchItem]:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.punch.view")
    rows = await db.scalars(
        select(PunchItem)
        .where(
            PunchItem.organization_id == context.organization_id,
            PunchItem.project_id == project_id,
        )
        .order_by(PunchItem.number.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/punch",
    response_model=PunchItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_punch_item_route(
    project_id: UUID,
    payload: PunchItemCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PunchItem:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.punch.create")
    try:
        item = await create_punch_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(item)
        return item
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/projects/{project_id}/punch/{item_id}", response_model=PunchItemRead)
async def update_punch_item_route(
    project_id: UUID,
    item_id: UUID,
    payload: PunchItemUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PunchItem:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.punch.update")
    try:
        item = await update_punch_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            item_id=item_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(item)
        return item
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/punch/{item_id}/close", response_model=PunchItemRead)
async def close_punch_item_route(
    project_id: UUID,
    item_id: UUID,
    payload: VersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PunchItem:
    context = await build_access_context(db, session.membership_id)
    _project_permissions(context, project_id, "safety.punch.close")
    try:
        item = await close_punch_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            item_id=item_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(item)
        return item
    except (SafetyConflictError, SafetyValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
