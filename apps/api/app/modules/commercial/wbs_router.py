from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import DbSession
from app.modules.commercial.models import WBSCode
from app.modules.commercial.wbs_schemas import (
    WBSCodeCreate,
    WBSCodeDetailRead,
    WBSCodeRead,
    WBSCodeTreeRead,
    WBSCodeUpdate,
    WBSPathNode,
)
from app.modules.commercial.wbs_service import (
    WBSConflictError,
    WBSValidationError,
    create_wbs_code,
    get_wbs_context,
    get_wbs_tree_context,
    list_wbs_codes,
    update_wbs_code,
)
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["commercial-wbs"])


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
    if isinstance(exc, WBSConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/projects/{project_id}/commercial/wbs", response_model=list[WBSCodeRead])
async def list_wbs_codes_route(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[WBSCode]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.wbs.view")
    try:
        return await list_wbs_codes(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
        )
    except WBSValidationError as exc:
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/wbs/tree",
    response_model=list[WBSCodeTreeRead],
)
async def get_wbs_tree_route(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[WBSCodeTreeRead]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.wbs.view")
    try:
        rows = await get_wbs_tree_context(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
        )
    except WBSValidationError as exc:
        _domain_error(exc)
    return [
        WBSCodeTreeRead(
            **WBSCodeRead.model_validate(row).model_dump(),
            depth=depth,
            path_codes=list(path_codes),
            child_count=child_count,
        )
        for row, depth, path_codes, child_count in rows
    ]


@router.post(
    "/projects/{project_id}/commercial/wbs",
    response_model=WBSCodeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wbs_code_route(
    project_id: UUID,
    payload: WBSCodeCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> WBSCode:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.wbs.manage")
    try:
        row = await create_wbs_code(
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
    except (WBSConflictError, WBSValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/wbs/{wbs_id}",
    response_model=WBSCodeDetailRead,
)
async def get_wbs_code_route(
    project_id: UUID,
    wbs_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> WBSCodeDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.wbs.view")
    try:
        row, path, descendants, usage = await get_wbs_context(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            wbs_id=wbs_id,
        )
    except WBSValidationError as exc:
        if str(exc) == "WBS code was not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        _domain_error(exc)

    child_count = int(
        await db.scalar(
            select(func.count(WBSCode.id)).where(
                WBSCode.organization_id == context.organization_id,
                WBSCode.project_id == project_id,
                WBSCode.parent_id == row.id,
            )
        )
        or 0
    )
    return WBSCodeDetailRead(
        **WBSCodeRead.model_validate(row).model_dump(),
        path=[
            WBSPathNode(
                id=item.id,
                code=item.code,
                name=item.name,
                kind=item.kind,
                status=item.status,
            )
            for item in path
        ],
        child_count=child_count,
        descendant_count=len(descendants),
        direct_usage_count=usage.direct_count,
        subtree_usage_count=usage.subtree_count,
        usage_areas=list(usage.usage_areas),
        structure_locked=usage.subtree_count > 0,
    )


@router.patch(
    "/projects/{project_id}/commercial/wbs/{wbs_id}",
    response_model=WBSCodeRead,
)
async def update_wbs_code_route(
    project_id: UUID,
    wbs_id: UUID,
    payload: WBSCodeUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> WBSCode:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.wbs.manage")
    try:
        row = await update_wbs_code(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            wbs_id=wbs_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (WBSConflictError, WBSValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
