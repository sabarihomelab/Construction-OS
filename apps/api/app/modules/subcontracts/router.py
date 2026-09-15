from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.subcontracts.models import (
    Subcontract,
    SubcontractClaim,
    SubcontractClaimLine,
    SubcontractLine,
    SubcontractStatus,
)
from app.modules.subcontracts.review import reject_claim
from app.modules.subcontracts.schemas import (
    ClaimCertification,
    ClaimPayment,
    RevisionAction,
    SubcontractClaimCreate,
    SubcontractClaimLineCreate,
    SubcontractClaimLineRead,
    SubcontractClaimRead,
    SubcontractCreate,
    SubcontractLineCreate,
    SubcontractLineRead,
    SubcontractRead,
)
from app.modules.subcontracts.service import (
    SubcontractConflictError,
    SubcontractValidationError,
    add_claim_line,
    add_subcontract_line,
    certify_claim,
    create_claim,
    create_subcontract,
    record_claim_payment,
    submit_claim,
    transition_subcontract,
)

router = APIRouter(tags=["subcontracts"])


def _permission(context, project_id: UUID, key: str) -> None:
    scoped = {item: set(values) for item, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _error(exc: Exception) -> None:
    if isinstance(exc, SubcontractConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/projects/{project_id}/subcontracts", response_model=list[SubcontractRead])
async def list_subcontracts(project_id: UUID, db: DbSession, session: CurrentSession) -> list[Subcontract]:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.contract.view")
    rows = await db.scalars(
        select(Subcontract)
        .where(Subcontract.organization_id == context.organization_id, Subcontract.project_id == project_id)
        .order_by(Subcontract.created_at.desc())
    )
    return list(rows.all())


@router.post("/projects/{project_id}/subcontracts", response_model=SubcontractRead, status_code=status.HTTP_201_CREATED)
async def create_subcontract_route(project_id: UUID, payload: SubcontractCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> Subcontract:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.contract.create")
    try:
        row = await create_subcontract(db, organization_id=context.organization_id, project_id=project_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.get("/projects/{project_id}/subcontracts/{subcontract_id}/lines", response_model=list[SubcontractLineRead])
async def list_subcontract_lines(project_id: UUID, subcontract_id: UUID, db: DbSession, session: CurrentSession) -> list[SubcontractLine]:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.contract.view")
    rows = await db.scalars(select(SubcontractLine).where(SubcontractLine.organization_id == context.organization_id, SubcontractLine.project_id == project_id, SubcontractLine.subcontract_id == subcontract_id).order_by(SubcontractLine.line_number))
    return list(rows.all())


@router.post("/projects/{project_id}/subcontracts/{subcontract_id}/lines", response_model=SubcontractLineRead, status_code=status.HTTP_201_CREATED)
async def add_subcontract_line_route(project_id: UUID, subcontract_id: UUID, payload: SubcontractLineCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractLine:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.contract.manage")
    try:
        row = await add_subcontract_line(db, organization_id=context.organization_id, project_id=project_id, subcontract_id=subcontract_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


async def _contract_transition(project_id: UUID, subcontract_id: UUID, payload: RevisionAction, target: SubcontractStatus, permission: str, db: DbSession, session: CurrentSession) -> Subcontract:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, permission)
    try:
        row = await transition_subcontract(db, organization_id=context.organization_id, project_id=project_id, subcontract_id=subcontract_id, expected_revision=payload.expected_revision, target=target, actor_user_id=session.user_id, actor_membership_id=session.membership_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.post("/projects/{project_id}/subcontracts/{subcontract_id}/submit", response_model=SubcontractRead)
async def submit_subcontract(project_id: UUID, subcontract_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> Subcontract:
    return await _contract_transition(project_id, subcontract_id, payload, SubcontractStatus.SUBMITTED, "subcontracts.contract.submit", db, session)


@router.post("/projects/{project_id}/subcontracts/{subcontract_id}/approve", response_model=SubcontractRead)
async def approve_subcontract(project_id: UUID, subcontract_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> Subcontract:
    return await _contract_transition(project_id, subcontract_id, payload, SubcontractStatus.APPROVED, "subcontracts.contract.approve", db, session)


@router.post("/projects/{project_id}/subcontracts/{subcontract_id}/issue", response_model=SubcontractRead)
async def issue_subcontract(project_id: UUID, subcontract_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> Subcontract:
    return await _contract_transition(project_id, subcontract_id, payload, SubcontractStatus.ISSUED, "subcontracts.contract.issue", db, session)


@router.post("/projects/{project_id}/subcontracts/{subcontract_id}/activate", response_model=SubcontractRead)
async def activate_subcontract(project_id: UUID, subcontract_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> Subcontract:
    return await _contract_transition(project_id, subcontract_id, payload, SubcontractStatus.ACTIVE, "subcontracts.contract.manage", db, session)


@router.post("/projects/{project_id}/subcontracts/{subcontract_id}/complete", response_model=SubcontractRead)
async def complete_subcontract(project_id: UUID, subcontract_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> Subcontract:
    return await _contract_transition(project_id, subcontract_id, payload, SubcontractStatus.COMPLETED, "subcontracts.contract.manage", db, session)


@router.get("/projects/{project_id}/subcontract-claims", response_model=list[SubcontractClaimRead])
async def list_claims(project_id: UUID, db: DbSession, session: CurrentSession) -> list[SubcontractClaim]:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.view")
    rows = await db.scalars(select(SubcontractClaim).where(SubcontractClaim.organization_id == context.organization_id, SubcontractClaim.project_id == project_id).order_by(SubcontractClaim.period_to.desc()))
    return list(rows.all())


@router.post("/projects/{project_id}/subcontract-claims", response_model=SubcontractClaimRead, status_code=status.HTTP_201_CREATED)
async def create_claim_route(project_id: UUID, payload: SubcontractClaimCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractClaim:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.create")
    try:
        row = await create_claim(db, organization_id=context.organization_id, project_id=project_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.get("/projects/{project_id}/subcontract-claims/{claim_id}/lines", response_model=list[SubcontractClaimLineRead])
async def list_claim_lines(project_id: UUID, claim_id: UUID, db: DbSession, session: CurrentSession) -> list[SubcontractClaimLine]:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.view")
    rows = await db.scalars(select(SubcontractClaimLine).where(SubcontractClaimLine.organization_id == context.organization_id, SubcontractClaimLine.project_id == project_id, SubcontractClaimLine.claim_id == claim_id).order_by(SubcontractClaimLine.created_at))
    return list(rows.all())


@router.post("/projects/{project_id}/subcontract-claims/{claim_id}/lines", response_model=SubcontractClaimLineRead, status_code=status.HTTP_201_CREATED)
async def add_claim_line_route(project_id: UUID, claim_id: UUID, payload: SubcontractClaimLineCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractClaimLine:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.manage")
    try:
        row = await add_claim_line(db, organization_id=context.organization_id, project_id=project_id, claim_id=claim_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.post("/projects/{project_id}/subcontract-claims/{claim_id}/submit", response_model=SubcontractClaimRead)
async def submit_claim_route(project_id: UUID, claim_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractClaim:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.submit")
    try:
        row = await submit_claim(db, organization_id=context.organization_id, project_id=project_id, claim_id=claim_id, expected_revision=payload.expected_revision, actor_user_id=session.user_id, actor_membership_id=session.membership_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.post("/projects/{project_id}/subcontract-claims/{claim_id}/reject", response_model=SubcontractClaimRead)
async def reject_claim_route(project_id: UUID, claim_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractClaim:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.certify")
    try:
        row = await reject_claim(db, organization_id=context.organization_id, project_id=project_id, claim_id=claim_id, expected_revision=payload.expected_revision, actor_user_id=session.user_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.post("/projects/{project_id}/subcontract-claims/{claim_id}/certify", response_model=SubcontractClaimRead)
async def certify_claim_route(project_id: UUID, claim_id: UUID, payload: ClaimCertification, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractClaim:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.certify")
    try:
        row = await certify_claim(db, organization_id=context.organization_id, project_id=project_id, claim_id=claim_id, expected_revision=payload.expected_revision, other_deductions=payload.other_deductions, tax_withheld_amount=payload.tax_withheld_amount, actor_user_id=session.user_id, actor_membership_id=session.membership_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)


@router.post("/projects/{project_id}/subcontract-claims/{claim_id}/payment", response_model=SubcontractClaimRead)
async def record_claim_payment_route(project_id: UUID, claim_id: UUID, payload: ClaimPayment, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> SubcontractClaim:
    context = await build_access_context(db, session.membership_id)
    _permission(context, project_id, "subcontracts.claim.payment")
    try:
        row = await record_claim_payment(db, organization_id=context.organization_id, project_id=project_id, claim_id=claim_id, expected_revision=payload.expected_revision, payment_amount=payload.paid_amount, actor_user_id=session.user_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (SubcontractConflictError, SubcontractValidationError) as exc:
        await db.rollback()
        _error(exc)
