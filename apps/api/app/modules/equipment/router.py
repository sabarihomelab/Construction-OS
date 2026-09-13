from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.equipment.models import (
    EquipmentAsset,
    EquipmentMaintenance,
    Material,
    MaterialDelivery,
    ProjectEquipmentAssignment,
    ProjectMaterialPlan,
)
from app.modules.equipment.schemas import (
    EquipmentAssetCreate,
    EquipmentAssetRead,
    EquipmentAssetUpdate,
    EquipmentAssignmentCreate,
    EquipmentAssignmentEnd,
    EquipmentAssignmentRead,
    MaintenanceCreate,
    MaintenanceRead,
    MaintenanceUpdate,
    MaterialCreate,
    MaterialDeliveryCreate,
    MaterialDeliveryRead,
    MaterialDeliveryUpdate,
    MaterialPlanRead,
    MaterialPlanWrite,
    MaterialRead,
    MaterialUpdate,
)
from app.modules.equipment.service import (
    EquipmentConflictError,
    EquipmentValidationError,
    assign_equipment_to_project,
    create_equipment_asset,
    create_maintenance,
    create_material,
    create_material_delivery,
    end_equipment_assignment,
    update_equipment_asset,
    update_maintenance,
    update_material,
    update_material_delivery,
    upsert_material_plan,
)
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["equipment", "materials"])


def _org_permission(context, key: str) -> None:
    if key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _project_permission(context, project_id: UUID, key: str) -> None:
    scoped = {item: set(values) for item, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, EquipmentConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/equipment/assets", response_model=list[EquipmentAssetRead])
async def list_equipment_assets(db: DbSession, session: CurrentSession) -> list[EquipmentAsset]:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "equipment.asset.view")
    rows = await db.scalars(
        select(EquipmentAsset)
        .where(EquipmentAsset.organization_id == context.organization_id)
        .order_by(EquipmentAsset.asset_number)
    )
    return list(rows.all())


@router.post(
    "/equipment/assets",
    response_model=EquipmentAssetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_equipment_asset_route(
    payload: EquipmentAssetCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> EquipmentAsset:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "equipment.asset.manage")
    try:
        asset = await create_equipment_asset(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(asset)
        return asset
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/equipment/assets/{asset_id}", response_model=EquipmentAssetRead)
async def update_equipment_asset_route(
    asset_id: UUID,
    payload: EquipmentAssetUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> EquipmentAsset:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "equipment.asset.manage")
    try:
        asset = await update_equipment_asset(
            db,
            organization_id=context.organization_id,
            asset_id=asset_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(asset)
        return asset
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/equipment/assignments",
    response_model=list[EquipmentAssignmentRead],
)
async def list_equipment_assignments(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectEquipmentAssignment]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "equipment.assignment.view")
    rows = await db.scalars(
        select(ProjectEquipmentAssignment)
        .where(
            ProjectEquipmentAssignment.organization_id == context.organization_id,
            ProjectEquipmentAssignment.project_id == project_id,
        )
        .order_by(ProjectEquipmentAssignment.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/equipment/assignments",
    response_model=EquipmentAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_equipment_route(
    project_id: UUID,
    payload: EquipmentAssignmentCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectEquipmentAssignment:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "equipment.assignment.manage")
    try:
        row = await assign_equipment_to_project(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/equipment/assignments/{assignment_id}/end",
    response_model=EquipmentAssignmentRead,
)
async def end_equipment_assignment_route(
    project_id: UUID,
    assignment_id: UUID,
    payload: EquipmentAssignmentEnd,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectEquipmentAssignment:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "equipment.assignment.manage")
    try:
        row = await end_equipment_assignment(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
            end_date=payload.end_date,
            ending_meter=payload.ending_meter,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/equipment/maintenance", response_model=list[MaintenanceRead])
async def list_maintenance(db: DbSession, session: CurrentSession) -> list[EquipmentMaintenance]:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "equipment.maintenance.view")
    rows = await db.scalars(
        select(EquipmentMaintenance)
        .where(EquipmentMaintenance.organization_id == context.organization_id)
        .order_by(EquipmentMaintenance.due_date, EquipmentMaintenance.created_at)
    )
    return list(rows.all())


@router.post(
    "/equipment/maintenance",
    response_model=MaintenanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_maintenance_route(
    payload: MaintenanceCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> EquipmentMaintenance:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "equipment.maintenance.manage")
    try:
        row = await create_maintenance(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/equipment/maintenance/{maintenance_id}", response_model=MaintenanceRead)
async def update_maintenance_route(
    maintenance_id: UUID,
    payload: MaintenanceUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> EquipmentMaintenance:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "equipment.maintenance.manage")
    try:
        row = await update_maintenance(
            db,
            organization_id=context.organization_id,
            maintenance_id=maintenance_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/materials", response_model=list[MaterialRead])
async def list_materials(db: DbSession, session: CurrentSession) -> list[Material]:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "materials.material.view")
    rows = await db.scalars(
        select(Material)
        .where(Material.organization_id == context.organization_id)
        .order_by(Material.code)
    )
    return list(rows.all())


@router.post("/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material_route(
    payload: MaterialCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Material:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "materials.material.manage")
    try:
        row = await create_material(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/materials/{material_id}", response_model=MaterialRead)
async def update_material_route(
    material_id: UUID,
    payload: MaterialUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Material:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "materials.material.manage")
    try:
        row = await update_material(
            db,
            organization_id=context.organization_id,
            material_id=material_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/materials/plans", response_model=list[MaterialPlanRead])
async def list_material_plans(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectMaterialPlan]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.plan.view")
    rows = await db.scalars(
        select(ProjectMaterialPlan)
        .where(
            ProjectMaterialPlan.organization_id == context.organization_id,
            ProjectMaterialPlan.project_id == project_id,
        )
        .order_by(ProjectMaterialPlan.created_at)
    )
    return list(rows.all())


@router.put("/projects/{project_id}/materials/plans", response_model=MaterialPlanRead)
async def upsert_material_plan_route(
    project_id: UUID,
    payload: MaterialPlanWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectMaterialPlan:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.plan.manage")
    try:
        row = await upsert_material_plan(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/materials/deliveries",
    response_model=list[MaterialDeliveryRead],
)
async def list_material_deliveries(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MaterialDelivery]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.delivery.view")
    rows = await db.scalars(
        select(MaterialDelivery)
        .where(
            MaterialDelivery.organization_id == context.organization_id,
            MaterialDelivery.project_id == project_id,
        )
        .order_by(MaterialDelivery.delivered_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/materials/deliveries",
    response_model=MaterialDeliveryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_delivery_route(
    project_id: UUID,
    payload: MaterialDeliveryCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MaterialDelivery:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.delivery.manage")
    try:
        row = await create_material_delivery(
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
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/materials/deliveries/{delivery_id}",
    response_model=MaterialDeliveryRead,
)
async def update_material_delivery_route(
    project_id: UUID,
    delivery_id: UUID,
    payload: MaterialDeliveryUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MaterialDelivery:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.delivery.manage")
    try:
        row = await update_material_delivery(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            delivery_id=delivery_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EquipmentConflictError, EquipmentValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
