import json
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import DbSession
from app.modules.commercial.boq_schemas import (
    BOQAction,
    BOQCreate,
    BOQDetailRead,
    BOQImportApplyRead,
    BOQImportApplyRequest,
    BOQImportPreviewRead,
    BOQImportPreviewRequest,
    BOQItemCreate,
    BOQItemDelete,
    BOQItemRead,
    BOQItemUpdate,
    BOQRead,
    BOQRevisionRead,
    BOQUpdate,
)
from app.modules.commercial.boq_service import (
    BOQConflictError,
    BOQValidationError,
    add_boq_item,
    apply_boq_import,
    approve_boq,
    boq_csv_template,
    cancel_boq,
    create_boq,
    delete_boq_item,
    export_boq_csv,
    export_boq_revision_csv,
    get_boq_context,
    list_boq_revisions,
    list_boqs,
    preview_boq_import,
    update_boq,
    update_boq_item,
)
from app.modules.commercial.models import BOQ, BOQItem
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["commercial-boq"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, BOQConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _detail_payload(boq: BOQ, items: list[BOQItem], revision_count: int) -> BOQDetailRead:
    total = sum((Decimal(item.amount) for item in items), start=Decimal("0.00"))
    return BOQDetailRead(
        **BOQRead.model_validate(boq).model_dump(),
        items=[BOQItemRead.model_validate(item) for item in items],
        total_amount=total,
        item_count=len(items),
        mapped_item_count=sum(1 for item in items if item.wbs_code_id is not None),
        revision_count=revision_count,
        editable=boq.status.value == "draft",
    )


@router.get("/projects/{project_id}/commercial/boqs", response_model=list[BOQRead])
async def list_boqs_route(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[BOQ]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    try:
        return await list_boqs(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
        )
    except BOQValidationError as exc:
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/boqs",
    response_model=BOQRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_boq_route(
    project_id: UUID,
    payload: BOQCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQ:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        row = await create_boq(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/commercial/boqs/template.csv")
async def download_boq_template_route(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    return Response(
        boq_csv_template(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="boq-import-template.csv"'},
    )


@router.get("/projects/{project_id}/commercial/boqs/{boq_id}", response_model=BOQDetailRead)
async def get_boq_detail_route(
    project_id: UUID,
    boq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> BOQDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    try:
        boq, items, revision_count = await get_boq_context(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
        )
        return _detail_payload(boq, items, revision_count)
    except BOQValidationError as exc:
        _domain_error(exc)


@router.patch("/projects/{project_id}/commercial/boqs/{boq_id}", response_model=BOQRead)
async def update_boq_route(
    project_id: UUID,
    boq_id: UUID,
    payload: BOQUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQ:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        row = await update_boq(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/boqs/{boq_id}/items",
    response_model=BOQItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_boq_item_route(
    project_id: UUID,
    boq_id: UUID,
    payload: BOQItemCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQItem:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        row = await add_boq_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/commercial/boqs/{boq_id}/items/{item_id}",
    response_model=BOQItemRead,
)
async def update_boq_item_route(
    project_id: UUID,
    boq_id: UUID,
    item_id: UUID,
    payload: BOQItemUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQItem:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        row = await update_boq_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            item_id=item_id,
            expected_revision=payload.expected_revision,
            expected_boq_revision=payload.expected_boq_revision,
            changes=payload.model_dump(
                exclude={"expected_revision", "expected_boq_revision", "reason"},
                exclude_unset=True,
            ),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.delete(
    "/projects/{project_id}/commercial/boqs/{boq_id}/items/{item_id}",
    response_model=BOQRead,
)
async def delete_boq_item_route(
    project_id: UUID,
    boq_id: UUID,
    item_id: UUID,
    payload: BOQItemDelete,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQ:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        boq = await delete_boq_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            item_id=item_id,
            expected_revision=payload.expected_revision,
            expected_boq_revision=payload.expected_boq_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(boq)
        return boq
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/commercial/boqs/{boq_id}/approve", response_model=BOQRead)
async def approve_boq_route(
    project_id: UUID,
    boq_id: UUID,
    payload: BOQAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQ:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.approve")
    try:
        row = await approve_boq(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            expected_revision=payload.expected_revision,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/commercial/boqs/{boq_id}/cancel", response_model=BOQRead)
async def cancel_boq_route(
    project_id: UUID,
    boq_id: UUID,
    payload: BOQAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQ:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        row = await cancel_boq(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/boqs/{boq_id}/revisions",
    response_model=list[BOQRevisionRead],
)
async def list_boq_revisions_route(
    project_id: UUID,
    boq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[BOQRevisionRead]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    try:
        rows = await list_boq_revisions(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
        )
        return [
            BOQRevisionRead(
                id=row.id,
                boq_id=row.boq_id,
                version_number=row.version_number,
                approved_by_membership_id=row.approved_by_membership_id,
                approved_at=row.approved_at,
                reason=row.reason,
                snapshot=json.loads(row.snapshot_json),
            )
            for row in rows
        ]
    except BOQValidationError as exc:
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/boqs/{boq_id}/import/preview",
    response_model=BOQImportPreviewRead,
)
async def preview_boq_import_route(
    project_id: UUID,
    boq_id: UUID,
    payload: BOQImportPreviewRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQImportPreviewRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        _boq, rows, total = await preview_boq_import(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            csv_text=payload.csv_text,
        )
        invalid_rows = sum(1 for row in rows if row["errors"])
        return BOQImportPreviewRead(
            rows=rows,
            valid_rows=len(rows) - invalid_rows,
            invalid_rows=invalid_rows,
            total_amount=total,
        )
    except (BOQConflictError, BOQValidationError) as exc:
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/boqs/{boq_id}/import/apply",
    response_model=BOQImportApplyRead,
)
async def apply_boq_import_route(
    project_id: UUID,
    boq_id: UUID,
    payload: BOQImportApplyRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> BOQImportApplyRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.manage")
    try:
        count, total, boq = await apply_boq_import(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            expected_revision=payload.expected_revision,
            csv_text=payload.csv_text,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        return BOQImportApplyRead(
            imported_rows=count,
            total_amount=total,
            boq_revision=boq.revision,
        )
    except (BOQConflictError, BOQValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/commercial/boqs/{boq_id}/export.csv")
async def export_boq_csv_route(
    project_id: UUID,
    boq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    try:
        filename, content = await export_boq_csv(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
        )
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except BOQValidationError as exc:
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/boqs/{boq_id}/revisions/{version_number}/export.csv"
)
async def export_boq_revision_csv_route(
    project_id: UUID,
    boq_id: UUID,
    version_number: int,
    db: DbSession,
    session: CurrentSession,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    try:
        filename, content = await export_boq_revision_csv(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            boq_id=boq_id,
            version_number=version_number,
        )
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except BOQValidationError as exc:
        _domain_error(exc)
