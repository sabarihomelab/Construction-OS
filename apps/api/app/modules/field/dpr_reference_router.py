from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.commercial.models import BOQ, BOQItem, BOQStatus, RecordStatus, WBSCode
from app.modules.features.service import build_access_context
from app.modules.field.dpr_reference_schemas import (
    DPRWorkProgressBOQItemReferenceRead,
    DPRWorkProgressReferenceRead,
    DPRWorkProgressWBSReferenceRead,
)
from app.modules.field.router import _require_permission
from app.modules.sessions.deps import CurrentSession

router = APIRouter(tags=["daily-progress-reports"])


@router.get(
    "/projects/{project_id}/daily-reports/work-progress/references",
    response_model=DPRWorkProgressReferenceRead,
)
async def get_work_progress_references(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DPRWorkProgressReferenceRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")

    wbs_rows = list(
        (
            await db.scalars(
                select(WBSCode)
                .where(
                    WBSCode.organization_id == context.organization_id,
                    WBSCode.project_id == project_id,
                    WBSCode.status == RecordStatus.ACTIVE,
                )
                .order_by(WBSCode.code, WBSCode.id)
            )
        ).all()
    )
    boq_rows = list(
        (
            await db.execute(
                select(BOQItem, BOQ)
                .join(BOQ, BOQ.id == BOQItem.boq_id)
                .where(
                    BOQItem.organization_id == context.organization_id,
                    BOQItem.project_id == project_id,
                    BOQ.organization_id == context.organization_id,
                    BOQ.project_id == project_id,
                    BOQ.status == BOQStatus.APPROVED,
                )
                .order_by(BOQ.code, BOQItem.line_number, BOQItem.id)
            )
        ).all()
    )

    return DPRWorkProgressReferenceRead(
        wbs_codes=[DPRWorkProgressWBSReferenceRead.model_validate(row) for row in wbs_rows],
        boq_items=[
            DPRWorkProgressBOQItemReferenceRead(
                id=item.id,
                boq_id=boq.id,
                boq_code=boq.code,
                boq_name=boq.name,
                wbs_code_id=item.wbs_code_id,
                item_code=item.item_code,
                description=item.description,
                unit_code=item.unit_code,
            )
            for item, boq in boq_rows
        ],
    )
