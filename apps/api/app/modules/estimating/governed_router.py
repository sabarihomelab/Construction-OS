from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import DbSession
from app.modules.estimating import service as legacy
from app.modules.estimating.governed_schemas import (
    ApprovalSnapshotRead,
    BudgetDetailRead,
    EstimateCopyBOQRequest,
    EstimateDetailRead,
    EstimateRevisionRequest,
    RateAnalysisDetailRead,
)
from app.modules.estimating.governed_service import (
    EstimatingConflictError,
    EstimatingValidationError,
    approve_budget,
    approve_estimate,
    copy_source_boq_items,
    create_budget_from_estimate,
    create_estimate,
    create_rate_analysis,
    list_budget_snapshots,
    list_estimate_snapshots,
    rate_breakdown,
    revise_estimate,
    submit_estimate,
    add_estimate_item,
)
from app.modules.estimating.history_models import BudgetApprovalSnapshot, EstimateApprovalSnapshot
from app.modules.estimating.models import (
    BudgetLine,
    EstimateItem,
    ProjectBudget,
    ProjectEstimate,
    RateAnalysis,
    RateAnalysisComponent,
)
from app.modules.estimating.schemas import (
    BudgetCreate,
    BudgetLineCreate,
    BudgetLineRead,
    BudgetRead,
    EstimateCreate,
    EstimateItemCreate,
    EstimateItemRead,
    EstimateRead,
    RateAnalysisCreate,
    RateAnalysisRead,
    RateComponentRead,
    RevisionAction,
)
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["estimating"])


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
    if isinstance(exc, EstimatingConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _estimate_detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
) -> EstimateDetailRead:
    estimate = await db.scalar(
        select(ProjectEstimate).where(
            ProjectEstimate.id == estimate_id,
            ProjectEstimate.organization_id == organization_id,
            ProjectEstimate.project_id == project_id,
        )
    )
    if estimate is None:
        raise EstimatingValidationError("Estimate was not found")
    items = list(
        (
            await db.scalars(
                select(EstimateItem)
                .where(
                    EstimateItem.organization_id == organization_id,
                    EstimateItem.project_id == project_id,
                    EstimateItem.estimate_id == estimate_id,
                )
                .order_by(EstimateItem.line_number)
            )
        ).all()
    )
    snapshots = int(
        await db.scalar(
            select(func.count(EstimateApprovalSnapshot.id)).where(
                EstimateApprovalSnapshot.estimate_id == estimate_id
            )
        )
        or 0
    )
    total = sum((Decimal(item.amount) for item in items), start=Decimal("0"))
    return EstimateDetailRead(
        **EstimateRead.model_validate(estimate).model_dump(),
        items=[EstimateItemRead.model_validate(item) for item in items],
        item_count=len(items),
        total_selling_amount=total,
        approval_snapshot_count=snapshots,
    )


async def _budget_detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    budget_id: UUID,
) -> BudgetDetailRead:
    budget = await db.scalar(
        select(ProjectBudget).where(
            ProjectBudget.id == budget_id,
            ProjectBudget.organization_id == organization_id,
            ProjectBudget.project_id == project_id,
        )
    )
    if budget is None:
        raise EstimatingValidationError("Budget was not found")
    lines = list(
        (
            await db.scalars(
                select(BudgetLine)
                .where(
                    BudgetLine.organization_id == organization_id,
                    BudgetLine.project_id == project_id,
                    BudgetLine.budget_id == budget_id,
                )
                .order_by(BudgetLine.wbs_code_id, BudgetLine.category)
            )
        ).all()
    )
    snapshots = int(
        await db.scalar(
            select(func.count(BudgetApprovalSnapshot.id)).where(
                BudgetApprovalSnapshot.budget_id == budget_id
            )
        )
        or 0
    )
    return BudgetDetailRead(
        **BudgetRead.model_validate(budget).model_dump(),
        lines=[BudgetLineRead.model_validate(line) for line in lines],
        line_count=len(lines),
        total_amount=sum((Decimal(line.amount) for line in lines), start=Decimal("0")),
        approval_snapshot_count=snapshots,
    )


@router.get("/projects/{project_id}/estimating/estimates", response_model=list[EstimateRead])
async def list_estimates_route(project_id: UUID, db: DbSession, session: CurrentSession):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.view")
    rows = await db.scalars(
        select(ProjectEstimate)
        .where(
            ProjectEstimate.organization_id == context.organization_id,
            ProjectEstimate.project_id == project_id,
        )
        .order_by(ProjectEstimate.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/estimating/estimates",
    response_model=EstimateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_estimate_route(
    project_id: UUID,
    payload: EstimateCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.manage")
    try:
        row = await create_estimate(
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
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/estimating/estimates/{estimate_id}",
    response_model=EstimateDetailRead,
)
async def estimate_detail_route(
    project_id: UUID,
    estimate_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.view")
    try:
        return await _estimate_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
        )
    except EstimatingValidationError as exc:
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/copy-boq-items",
    response_model=EstimateRead,
)
async def copy_boq_items_route(
    project_id: UUID,
    estimate_id: UUID,
    payload: EstimateCopyBOQRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.manage")
    try:
        row = await copy_source_boq_items(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/items",
    response_model=EstimateItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_estimate_item_route(
    project_id: UUID,
    estimate_id: UUID,
    payload: EstimateItemCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.manage")
    try:
        row = await add_estimate_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/rate-analyses",
    response_model=RateAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rate_analysis_route(
    project_id: UUID,
    payload: RateAnalysisCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.rate_analysis.manage")
    try:
        analysis = await create_rate_analysis(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        components = list(
            (
                await db.scalars(
                    select(RateAnalysisComponent)
                    .where(RateAnalysisComponent.analysis_id == analysis.id)
                    .order_by(RateAnalysisComponent.created_at)
                )
            ).all()
        )
        return RateAnalysisRead(
            id=analysis.id,
            project_id=analysis.project_id,
            estimate_item_id=analysis.estimate_item_id,
            version_number=analysis.version_number,
            wastage_percent=analysis.wastage_percent,
            overhead_percent=analysis.overhead_percent,
            profit_percent=analysis.profit_percent,
            calculated_rate=analysis.calculated_rate,
            is_current=analysis.is_current,
            notes=analysis.notes,
            components=[RateComponentRead.model_validate(item) for item in components],
        )
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/estimating/estimate-items/{item_id}/rate-analysis",
    response_model=RateAnalysisDetailRead,
)
async def current_rate_analysis_route(
    project_id: UUID,
    item_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.view")
    item = await db.scalar(
        select(EstimateItem).where(
            EstimateItem.id == item_id,
            EstimateItem.organization_id == context.organization_id,
            EstimateItem.project_id == project_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Estimate item was not found")
    analysis = await db.scalar(
        select(RateAnalysis).where(
            RateAnalysis.estimate_item_id == item_id,
            RateAnalysis.is_current.is_(True),
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Current rate analysis was not found")
    components = list(
        (
            await db.scalars(
                select(RateAnalysisComponent)
                .where(RateAnalysisComponent.analysis_id == analysis.id)
                .order_by(RateAnalysisComponent.created_at)
            )
        ).all()
    )
    base = sum((Decimal(row.amount) for row in components), start=Decimal("0"))
    breakdown = rate_breakdown(
        base,
        Decimal(analysis.wastage_percent),
        Decimal(analysis.overhead_percent),
        Decimal(analysis.profit_percent),
    )
    return RateAnalysisDetailRead(
        id=analysis.id,
        project_id=analysis.project_id,
        estimate_item_id=analysis.estimate_item_id,
        version_number=analysis.version_number,
        wastage_percent=analysis.wastage_percent,
        overhead_percent=analysis.overhead_percent,
        profit_percent=analysis.profit_percent,
        calculated_rate=analysis.calculated_rate,
        is_current=analysis.is_current,
        notes=analysis.notes,
        components=[RateComponentRead.model_validate(row) for row in components],
        **breakdown,
    )


@router.post(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/submit",
    response_model=EstimateRead,
)
async def submit_estimate_route(
    project_id: UUID,
    estimate_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.submit")
    try:
        row = await submit_estimate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            actor_membership_id=session.membership_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/approve",
    response_model=EstimateRead,
)
async def approve_estimate_route(
    project_id: UUID,
    estimate_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.approve")
    try:
        row = await approve_estimate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            actor_membership_id=session.membership_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/revise",
    response_model=EstimateRead,
    status_code=status.HTTP_201_CREATED,
)
async def revise_estimate_route(
    project_id: UUID,
    estimate_id: UUID,
    payload: EstimateRevisionRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.manage")
    try:
        row = await revise_estimate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            new_code=payload.new_code,
            new_name=payload.new_name,
            reason=payload.reason,
            actor_user_id=session.user_id,
            actor_membership_id=session.membership_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/approvals",
    response_model=list[ApprovalSnapshotRead],
)
async def estimate_approvals_route(
    project_id: UUID,
    estimate_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.view")
    try:
        rows = await list_estimate_snapshots(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
        )
        return [ApprovalSnapshotRead.from_row(row) for row in rows]
    except EstimatingValidationError as exc:
        _domain_error(exc)


@router.get("/projects/{project_id}/estimating/budgets", response_model=list[BudgetRead])
async def list_budgets_route(project_id: UUID, db: DbSession, session: CurrentSession):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.view")
    rows = await db.scalars(
        select(ProjectBudget)
        .where(
            ProjectBudget.organization_id == context.organization_id,
            ProjectBudget.project_id == project_id,
        )
        .order_by(ProjectBudget.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/estimating/budgets",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_budget_route(
    project_id: UUID,
    payload: BudgetCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.manage")
    try:
        row = await legacy.create_budget(
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
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/estimates/{estimate_id}/budget",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_budget_route(
    project_id: UUID,
    estimate_id: UUID,
    payload: BudgetCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.manage")
    try:
        row = await create_budget_from_estimate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            code=payload.code,
            name=payload.name,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/estimating/budgets/{budget_id}",
    response_model=BudgetDetailRead,
)
async def budget_detail_route(
    project_id: UUID,
    budget_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.view")
    try:
        return await _budget_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            budget_id=budget_id,
        )
    except EstimatingValidationError as exc:
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/budgets/{budget_id}/lines",
    response_model=BudgetLineRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_budget_line_route(
    project_id: UUID,
    budget_id: UUID,
    payload: BudgetLineCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.manage")
    try:
        row = await legacy.add_budget_line(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            budget_id=budget_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/estimating/budgets/{budget_id}/approve",
    response_model=BudgetRead,
)
async def approve_budget_route(
    project_id: UUID,
    budget_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.approve")
    try:
        row = await approve_budget(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            budget_id=budget_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            actor_membership_id=session.membership_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (EstimatingConflictError, EstimatingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/estimating/budgets/{budget_id}/approvals",
    response_model=list[ApprovalSnapshotRead],
)
async def budget_approvals_route(
    project_id: UUID,
    budget_id: UUID,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.view")
    try:
        rows = await list_budget_snapshots(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            budget_id=budget_id,
        )
        return [ApprovalSnapshotRead.from_row(row) for row in rows]
    except EstimatingValidationError as exc:
        _domain_error(exc)
