from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.commitment_feeds import post_purchase_order_commitment
from app.modules.financials.commitment_models import ProjectCommitmentAllocation
from app.modules.financials.commitment_schemas import (
    ProjectCommitmentAllocationRead,
    ProjectCommitmentDetailRead,
)
from app.modules.financials.models import ProjectCommitment
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


async def _detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    commitment: ProjectCommitment,
) -> ProjectCommitmentDetailRead:
    allocations = list(
        (
            await db.scalars(
                select(ProjectCommitmentAllocation)
                .where(
                    ProjectCommitmentAllocation.organization_id == organization_id,
                    ProjectCommitmentAllocation.project_id == project_id,
                    ProjectCommitmentAllocation.commitment_id == commitment.id,
                )
                .order_by(ProjectCommitmentAllocation.line_number)
            )
        ).all()
    )
    return ProjectCommitmentDetailRead(
        id=commitment.id,
        organization_id=commitment.organization_id,
        project_id=commitment.project_id,
        source_type=commitment.source_type,
        source_id=commitment.source_id,
        source_number=commitment.source_number,
        party_id=commitment.party_id,
        wbs_code_id=commitment.wbs_code_id,
        committed_amount=commitment.committed_amount,
        currency_code=commitment.currency_code,
        status=commitment.status,
        committed_at=commitment.committed_at,
        closed_at=commitment.closed_at,
        revision=commitment.revision,
        allocations=[
            ProjectCommitmentAllocationRead.model_validate(item) for item in allocations
        ],
    )


@router.get(
    "/projects/{project_id}/financials/commitments",
    response_model=list[ProjectCommitmentDetailRead],
)
async def list_project_commitments(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectCommitmentDetailRead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.project_cost.view")
    rows = list(
        (
            await db.scalars(
                select(ProjectCommitment)
                .where(
                    ProjectCommitment.organization_id == context.organization_id,
                    ProjectCommitment.project_id == project_id,
                )
                .order_by(ProjectCommitment.committed_at.desc())
            )
        ).all()
    )
    return [
        await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            commitment=row,
        )
        for row in rows
    ]


@router.post(
    "/projects/{project_id}/financials/commitments/from-purchase-orders/{purchase_order_id}",
    response_model=ProjectCommitmentDetailRead,
)
async def post_purchase_order_project_commitment(
    project_id: UUID,
    purchase_order_id: UUID,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectCommitmentDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.project_cost.post")
    try:
        row = await post_purchase_order_commitment(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            purchase_order_id=purchase_order_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            commitment=row,
        )
    except FinancialConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FinancialValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
