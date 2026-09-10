from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.estimating.models import (
    BudgetLine,
    EstimateItem,
    EstimateStatus,
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
from app.modules.estimating.service import (
    EstimatingConflictError,
    EstimatingValidationError,
    add_budget_line,
    add_estimate_item,
    approve_budget,
    create_budget,
    create_budget_from_estimate,
    create_estimate,
    create_rate_analysis,
    transition_estimate,
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


@router.get("/projects/{project_id}/estimating/estimates", response_model=list[EstimateRead])
async def list_estimates(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectEstimate]:
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
) -> ProjectEstimate:
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
    "/projects/{project_id}/estimating/estimates/{estimate_id}/items",
    response_model=list[EstimateItemRead],
)
async def list_estimate_items(
    project_id: UUID,
    estimate_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[EstimateItem]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.view")
    rows = await db.scalars(
        select(EstimateItem)
        .where(
            EstimateItem.organization_id == context.organization_id,
            EstimateItem.project_id == project_id,
            EstimateItem.estimate_id == estimate_id,
        )
        .order_by(EstimateItem.line_number)
    )
    return list(rows.all())


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
) -> EstimateItem:
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
) -> RateAnalysisRead:
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


@router.post("/projects/{project_id}/estimating/estimates/{estimate_id}/submit", response_model=EstimateRead)
async def submit_estimate(
    project_id: UUID,
    estimate_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectEstimate:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.submit")
    try:
        row = await transition_estimate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            expected_revision=payload.expected_revision,
            target=EstimateStatus.SUBMITTED,
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


@router.post("/projects/{project_id}/estimating/estimates/{estimate_id}/approve", response_model=EstimateRead)
async def approve_estimate(
    project_id: UUID,
    estimate_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectEstimate:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.estimate.approve")
    try:
        row = await transition_estimate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            estimate_id=estimate_id,
            expected_revision=payload.expected_revision,
            target=EstimateStatus.APPROVED,
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


@router.get("/projects/{project_id}/estimating/budgets", response_model=list[BudgetRead])
async def list_budgets(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectBudget]:
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
) -> ProjectBudget:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.manage")
    try:
        row = await create_budget(
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
async def generate_budget_from_estimate(
    project_id: UUID,
    estimate_id: UUID,
    payload: BudgetCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectBudget:
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
    "/projects/{project_id}/estimating/budgets/{budget_id}/lines",
    response_model=list[BudgetLineRead],
)
async def list_budget_lines(
    project_id: UUID,
    budget_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[BudgetLine]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.view")
    rows = await db.scalars(
        select(BudgetLine)
        .where(
            BudgetLine.organization_id == context.organization_id,
            BudgetLine.project_id == project_id,
            BudgetLine.budget_id == budget_id,
        )
        .order_by(BudgetLine.created_at)
    )
    return list(rows.all())


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
) -> BudgetLine:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "estimating.budget.manage")
    try:
        row = await add_budget_line(
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


@router.post("/projects/{project_id}/estimating/budgets/{budget_id}/approve", response_model=BudgetRead)
async def approve_budget_route(
    project_id: UUID,
    budget_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectBudget:
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
