from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.rfis.models import RFI, RFIHistoryEvent, RFIReference, RFIResponse
from app.modules.rfis.schemas import (
    RFIBallInCourtUpdate,
    RFICreate,
    RFIHistoryRead,
    RFIRead,
    RFIReferenceCreate,
    RFIReferenceRead,
    RFIResponseCreate,
    RFIResponseRead,
    RFIUpdate,
    RFIVersionAction,
    RFIVoidRequest,
)
from app.modules.rfis.service import (
    RFIConflictError,
    RFIValidationError,
    add_reference,
    add_response,
    close_rfi,
    create_rfi,
    open_rfi,
    set_ball_in_court,
    update_rfi,
    void_rfi,
)
from app.modules.sessions.deps import CurrentSession

router = APIRouter(prefix="/projects/{project_id}/rfis", tags=["rfis"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    project_permissions = {
        key: set(values) for key, values in context.project_permissions.items()
    }
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


async def _load_rfi_or_404(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfi_id: UUID,
) -> RFI:
    rfi = await db.scalar(
        select(RFI).where(
            RFI.id == rfi_id,
            RFI.organization_id == organization_id,
            RFI.project_id == project_id,
        )
    )
    if rfi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFI not found")
    return rfi


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, RFIConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=list[RFIRead])
async def list_rfis(project_id: UUID, db: DbSession, session: CurrentSession) -> list[RFI]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.view")
    rows = await db.scalars(
        select(RFI)
        .where(
            RFI.organization_id == context.organization_id,
            RFI.project_id == project_id,
        )
        .order_by(RFI.number.desc())
    )
    return list(rows.all())


@router.post("", response_model=RFIRead, status_code=status.HTTP_201_CREATED)
async def create_rfi_route(
    project_id: UUID,
    payload: RFICreate,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.create")
    try:
        rfi = await create_rfi(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            **payload.model_dump(),
        )
        await db.commit()
        await db.refresh(rfi)
        return rfi
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{rfi_id}", response_model=RFIRead)
async def get_rfi(
    project_id: UUID,
    rfi_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.view")
    return await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )


@router.patch("/{rfi_id}", response_model=RFIRead)
async def patch_rfi(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIUpdate,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.update")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        rfi = await update_rfi(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            expected_version=payload.expected_version,
            changes=payload.model_dump(exclude={"expected_version"}, exclude_unset=True),
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(rfi)
        return rfi
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{rfi_id}/open", response_model=RFIRead)
async def open_rfi_route(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIVersionAction,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.update")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        rfi = await open_rfi(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(rfi)
        return rfi
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.put("/{rfi_id}/ball-in-court", response_model=RFIRead)
async def update_ball_in_court(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIBallInCourtUpdate,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.manage")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        rfi = await set_ball_in_court(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            expected_version=payload.expected_version,
            membership_id=payload.membership_id,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(rfi)
        return rfi
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{rfi_id}/responses", response_model=list[RFIResponseRead])
async def list_responses(
    project_id: UUID,
    rfi_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RFIResponse]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.view")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    rows = await db.scalars(
        select(RFIResponse)
        .where(
            RFIResponse.organization_id == context.organization_id,
            RFIResponse.rfi_id == rfi_id,
        )
        .order_by(RFIResponse.sequence)
    )
    return list(rows.all())


@router.post(
    "/{rfi_id}/responses",
    response_model=RFIResponseRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_response_route(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIResponseCreate,
    db: DbSession,
    session: CurrentSession,
) -> RFIResponse:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.respond")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        response = await add_response(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            response_text=payload.response_text,
            actor_user_id=session.user_id,
            official=payload.official,
        )
        await db.commit()
        await db.refresh(response)
        return response
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{rfi_id}/references", response_model=list[RFIReferenceRead])
async def list_references(
    project_id: UUID,
    rfi_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RFIReference]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.view")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    rows = await db.scalars(
        select(RFIReference)
        .where(
            RFIReference.organization_id == context.organization_id,
            RFIReference.rfi_id == rfi_id,
        )
        .order_by(RFIReference.created_at, RFIReference.id)
    )
    return list(rows.all())


@router.post(
    "/{rfi_id}/references",
    response_model=RFIReferenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_reference_route(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIReferenceCreate,
    db: DbSession,
    session: CurrentSession,
) -> RFIReference:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.update")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        reference = await add_reference(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            label=payload.label,
        )
        await db.commit()
        await db.refresh(reference)
        return reference
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{rfi_id}/history", response_model=list[RFIHistoryRead])
async def list_history(
    project_id: UUID,
    rfi_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RFIHistoryEvent]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.view")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    rows = await db.scalars(
        select(RFIHistoryEvent)
        .where(
            RFIHistoryEvent.organization_id == context.organization_id,
            RFIHistoryEvent.rfi_id == rfi_id,
        )
        .order_by(RFIHistoryEvent.created_at, RFIHistoryEvent.id)
    )
    return list(rows.all())


@router.post("/{rfi_id}/close", response_model=RFIRead)
async def close_rfi_route(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIVersionAction,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.close")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        rfi = await close_rfi(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(rfi)
        return rfi
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{rfi_id}/void", response_model=RFIRead)
async def void_rfi_route(
    project_id: UUID,
    rfi_id: UUID,
    payload: RFIVoidRequest,
    db: DbSession,
    session: CurrentSession,
) -> RFI:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "rfis.rfi.manage")
    await _load_rfi_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        rfi_id=rfi_id,
    )
    try:
        rfi = await void_rfi(
            db,
            organization_id=context.organization_id,
            rfi_id=rfi_id,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(rfi)
        return rfi
    except (RFIValidationError, RFIConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)
