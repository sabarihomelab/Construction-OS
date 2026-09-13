from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.commercial.models import (
    BOQ,
    BOQItem,
    MeasurementEntry,
    MeasurementStatus,
    Party,
    ProjectPartyAssignment,
    RABill,
    RABillLine,
    RABillStatus,
    WBSCode,
)
from app.modules.commercial.schemas import (
    BOQCreate,
    BOQDetailRead,
    BOQItemCreate,
    BOQItemRead,
    BOQItemUpdate,
    BOQRead,
    CommercialDashboardRead,
    MeasurementCreate,
    MeasurementRead,
    MeasurementReview,
    PartyCreate,
    PartyRead,
    PartyUpdate,
    ProjectPartyAssignmentCreate,
    ProjectPartyAssignmentRead,
    RABillCreate,
    RABillDetailRead,
    RABillLineRead,
    RABillRead,
    RevisionAction,
    WBSCodeCreate,
    WBSCodeRead,
    WBSCodeUpdate,
)
from app.modules.commercial.service import (
    CommercialConflictError,
    CommercialValidationError,
    add_boq_item,
    approve_boq,
    assign_party_to_project,
    commercial_dashboard,
    create_boq,
    create_measurement,
    create_party,
    create_ra_bill,
    create_wbs_code,
    transition_measurement,
    transition_ra_bill,
    update_boq_item,
    update_party,
    update_wbs_code,
)
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["commercial"])


def _org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


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
    if isinstance(exc, CommercialConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/commercial/parties", response_model=list[PartyRead])
async def list_parties(db: DbSession, session: CurrentSession) -> list[Party]:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "commercial.party.view")
    rows = await db.scalars(
        select(Party)
        .where(Party.organization_id == context.organization_id)
        .order_by(Party.name, Party.code)
    )
    return list(rows.all())


@router.post(
    "/commercial/parties",
    response_model=PartyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_party_route(
    payload: PartyCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Party:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "commercial.party.manage")
    try:
        row = await create_party(
            db,
            organization_id=context.organization_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/commercial/parties/{party_id}", response_model=PartyRead)
async def update_party_route(
    party_id: UUID,
    payload: PartyUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Party:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "commercial.party.manage")
    try:
        row = await update_party(
            db,
            organization_id=context.organization_id,
            party_id=party_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/parties",
    response_model=list[ProjectPartyAssignmentRead],
)
async def list_project_parties(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectPartyAssignment]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.party.view")
    rows = await db.scalars(
        select(ProjectPartyAssignment)
        .where(
            ProjectPartyAssignment.organization_id == context.organization_id,
            ProjectPartyAssignment.project_id == project_id,
            ProjectPartyAssignment.active.is_(True),
        )
        .order_by(ProjectPartyAssignment.role)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/commercial/parties",
    response_model=ProjectPartyAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_project_party_route(
    project_id: UUID,
    payload: ProjectPartyAssignmentCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectPartyAssignment:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.party.manage")
    try:
        row = await assign_party_to_project(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            party_id=payload.party_id,
            role=payload.role,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/commercial/wbs", response_model=list[WBSCodeRead])
async def list_wbs_codes(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[WBSCode]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.wbs.view")
    rows = await db.scalars(
        select(WBSCode)
        .where(
            WBSCode.organization_id == context.organization_id,
            WBSCode.project_id == project_id,
        )
        .order_by(WBSCode.code)
    )
    return list(rows.all())


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
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/projects/{project_id}/commercial/wbs/{wbs_id}", response_model=WBSCodeRead)
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
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/commercial/boqs", response_model=list[BOQRead])
async def list_boqs(project_id: UUID, db: DbSession, session: CurrentSession) -> list[BOQ]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    rows = await db.scalars(
        select(BOQ)
        .where(BOQ.organization_id == context.organization_id, BOQ.project_id == project_id)
        .order_by(BOQ.created_at.desc())
    )
    return list(rows.all())


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
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/commercial/boqs/{boq_id}", response_model=BOQDetailRead)
async def get_boq_detail(
    project_id: UUID,
    boq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> BOQDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    boq = await db.scalar(
        select(BOQ).where(
            BOQ.id == boq_id,
            BOQ.organization_id == context.organization_id,
            BOQ.project_id == project_id,
        )
    )
    if boq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOQ not found")
    items = list(
        (
            await db.scalars(
                select(BOQItem).where(BOQItem.boq_id == boq_id).order_by(BOQItem.line_number)
            )
        ).all()
    )
    return BOQDetailRead(
        **BOQRead.model_validate(boq).model_dump(),
        items=[BOQItemRead.model_validate(item) for item in items],
        total_amount=sum((Decimal(item.amount) for item in items), start=Decimal("0.00")),
    )


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
    except (CommercialConflictError, CommercialValidationError) as exc:
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
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/commercial/boqs/{boq_id}/approve", response_model=BOQRead)
async def approve_boq_route(
    project_id: UUID,
    boq_id: UUID,
    payload: RevisionAction,
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
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/measurements",
    response_model=list[MeasurementRead],
)
async def list_measurements(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeasurementEntry]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.measurement.view")
    rows = await db.scalars(
        select(MeasurementEntry)
        .where(
            MeasurementEntry.organization_id == context.organization_id,
            MeasurementEntry.project_id == project_id,
        )
        .order_by(MeasurementEntry.entry_number.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/commercial/measurements",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement_route(
    project_id: UUID,
    payload: MeasurementCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeasurementEntry:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.measurement.create")
    try:
        row = await create_measurement(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/measurements/{measurement_id}/submit",
    response_model=MeasurementRead,
)
async def submit_measurement_route(
    project_id: UUID,
    measurement_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeasurementEntry:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.measurement.submit")
    try:
        row = await transition_measurement(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            measurement_id=measurement_id,
            expected_revision=payload.expected_revision,
            target_status=MeasurementStatus.SUBMITTED,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/measurements/{measurement_id}/review",
    response_model=MeasurementRead,
)
async def review_measurement_route(
    project_id: UUID,
    measurement_id: UUID,
    payload: MeasurementReview,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeasurementEntry:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.measurement.certify")
    target = MeasurementStatus.CERTIFIED if payload.approve else MeasurementStatus.REJECTED
    try:
        row = await transition_measurement(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            measurement_id=measurement_id,
            expected_revision=payload.expected_revision,
            target_status=target,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/commercial/ra-bills", response_model=list[RABillRead])
async def list_ra_bills(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RABill]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.ra_bill.view")
    rows = await db.scalars(
        select(RABill)
        .where(RABill.organization_id == context.organization_id, RABill.project_id == project_id)
        .order_by(RABill.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/commercial/ra-bills",
    response_model=RABillRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ra_bill_route(
    project_id: UUID,
    payload: RABillCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RABill:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.ra_bill.create")
    try:
        row = await create_ra_bill(
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
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/commercial/ra-bills/{bill_id}",
    response_model=RABillDetailRead,
)
async def get_ra_bill_detail(
    project_id: UUID,
    bill_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> RABillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.ra_bill.view")
    bill = await db.scalar(
        select(RABill).where(
            RABill.id == bill_id,
            RABill.organization_id == context.organization_id,
            RABill.project_id == project_id,
        )
    )
    if bill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RA bill not found")
    lines = list(
        (
            await db.scalars(
                select(RABillLine).where(RABillLine.ra_bill_id == bill.id).order_by(RABillLine.id)
            )
        ).all()
    )
    return RABillDetailRead(
        **RABillRead.model_validate(bill).model_dump(),
        lines=[RABillLineRead.model_validate(line) for line in lines],
    )


async def _transition_bill_route(
    *,
    project_id: UUID,
    bill_id: UUID,
    payload: RevisionAction,
    target_status: RABillStatus,
    permission_key: str,
    db: DbSession,
    session: CurrentSession,
) -> RABill:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, permission_key)
    try:
        row = await transition_ra_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill_id=bill_id,
            expected_revision=payload.expected_revision,
            target_status=target_status,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/commercial/ra-bills/{bill_id}/submit",
    response_model=RABillRead,
)
async def submit_ra_bill_route(
    project_id: UUID,
    bill_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RABill:
    return await _transition_bill_route(
        project_id=project_id,
        bill_id=bill_id,
        payload=payload,
        target_status=RABillStatus.SUBMITTED,
        permission_key="commercial.ra_bill.submit",
        db=db,
        session=session,
    )


@router.post(
    "/projects/{project_id}/commercial/ra-bills/{bill_id}/certify",
    response_model=RABillRead,
)
async def certify_ra_bill_route(
    project_id: UUID,
    bill_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RABill:
    return await _transition_bill_route(
        project_id=project_id,
        bill_id=bill_id,
        payload=payload,
        target_status=RABillStatus.CERTIFIED,
        permission_key="commercial.ra_bill.certify",
        db=db,
        session=session,
    )


@router.post(
    "/projects/{project_id}/commercial/ra-bills/{bill_id}/mark-paid",
    response_model=RABillRead,
)
async def mark_ra_bill_paid_route(
    project_id: UUID,
    bill_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RABill:
    return await _transition_bill_route(
        project_id=project_id,
        bill_id=bill_id,
        payload=payload,
        target_status=RABillStatus.PAID,
        permission_key="commercial.ra_bill.certify",
        db=db,
        session=session,
    )


@router.get(
    "/projects/{project_id}/commercial/dashboard",
    response_model=CommercialDashboardRead,
)
async def get_commercial_dashboard(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> dict[str, object]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")
    return await commercial_dashboard(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
    )
