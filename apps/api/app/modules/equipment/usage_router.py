from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.equipment.usage_models import EquipmentUsage, ProjectEquipmentRate
from app.modules.equipment.usage_schemas import (
    EquipmentUsageCreate,
    EquipmentUsagePost,
    EquipmentUsageRead,
    ProjectEquipmentRateCreate,
    ProjectEquipmentRateEnd,
    ProjectEquipmentRateRead,
)
from app.modules.equipment.usage_service import (
    EquipmentUsageConflictError,
    EquipmentUsageValidationError,
    create_equipment_rate,
    create_equipment_usage,
    end_equipment_rate,
    post_equipment_usage,
)
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["equipment"])


def _permission(context, project_id: UUID, key: str) -> None:
    if not project_permission_is_allowed(
        key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={item: set(values) for item, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, EquipmentUsageConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/equipment/usages",
    response_model=list[EquipmentUsageRead],
)
async def list_equipment_usages(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[EquipmentUsage]:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "equipment.usage.view")
    rows = await db.scalars(
        select(EquipmentUsage)
        .where(
            EquipmentUsage.organization_id == context.organization_id,
            EquipmentUsage.project_id == project_id,
        )
        .order_by(EquipmentUsage.usage_date.desc(), EquipmentUsage.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/equipment/usages",
    response_model=EquipmentUsageRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_equipment_usage_route(
    project_id: UUID,
    payload: EquipmentUsageCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> EquipmentUsage:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "equipment.usage.create")
    try:
        row = await create_equipment_usage(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentUsageConflictError, EquipmentUsageValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/equipment/usages/{usage_id}/post",
    response_model=EquipmentUsageRead,
)
async def post_equipment_usage_route(
    project_id: UUID,
    usage_id: UUID,
    payload: EquipmentUsagePost,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> EquipmentUsage:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "equipment.usage.post")
    try:
        row = await post_equipment_usage(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            usage_id=usage_id,
            membership_id=context.membership_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentUsageConflictError, EquipmentUsageValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/equipment/assignments/{assignment_id}/rates",
    response_model=list[ProjectEquipmentRateRead],
)
async def list_equipment_rates(
    project_id: UUID,
    assignment_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectEquipmentRate]:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "equipment.rate.view")
    rows = await db.scalars(
        select(ProjectEquipmentRate)
        .where(
            ProjectEquipmentRate.organization_id == context.organization_id,
            ProjectEquipmentRate.project_id == project_id,
            ProjectEquipmentRate.equipment_assignment_id == assignment_id,
        )
        .order_by(ProjectEquipmentRate.effective_from.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/equipment/assignments/{assignment_id}/rates",
    response_model=ProjectEquipmentRateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_equipment_rate_route(
    project_id: UUID,
    assignment_id: UUID,
    payload: ProjectEquipmentRateCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectEquipmentRate:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "equipment.rate.manage")
    try:
        row = await create_equipment_rate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentUsageConflictError, EquipmentUsageValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/equipment/assignments/{assignment_id}/rates/{rate_id}/end",
    response_model=ProjectEquipmentRateRead,
)
async def end_equipment_rate_route(
    project_id: UUID,
    assignment_id: UUID,
    rate_id: UUID,
    payload: ProjectEquipmentRateEnd,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectEquipmentRate:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "equipment.rate.manage")
    try:
        row = await end_equipment_rate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            rate_id=rate_id,
            membership_id=context.membership_id,
            expected_revision=payload.expected_revision,
            effective_to=payload.effective_to,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentUsageConflictError, EquipmentUsageValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
