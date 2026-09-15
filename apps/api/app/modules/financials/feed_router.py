from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.cost_feeds import post_approved_timecard_labour_cost
from app.modules.financials.feed_schemas import LabourTimeCostPost
from app.modules.financials.schemas import ProjectCostRead
from app.modules.financials.service import FinancialConflictError, FinancialValidationError
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.post(
    "/projects/{project_id}/financials/job-cost/from-timecards/{timecard_id}",
    response_model=ProjectCostRead,
)
async def post_timecard_labour_cost(
    project_id: UUID,
    timecard_id: UUID,
    payload: LabourTimeCostPost,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.project_cost.post")
    try:
        row = await post_approved_timecard_labour_cost(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            timecard_id=timecard_id,
            labour_cost_head_id=payload.labour_cost_head_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except FinancialConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FinancialValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
