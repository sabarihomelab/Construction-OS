from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.commercial.boq_field_schemas import BOQFieldReferenceRead
from app.modules.commercial.models import BOQ, BOQItem, BOQStatus
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession

router = APIRouter(tags=["commercial-boq-field"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/commercial/boqs/field-reference",
    response_model=list[BOQFieldReferenceRead],
)
async def list_field_boq_references(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[BOQFieldReferenceRead]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.boq.view")

    rows = (
        await db.execute(
            select(BOQItem, BOQ)
            .join(BOQ, BOQ.id == BOQItem.boq_id)
            .where(
                BOQ.organization_id == context.organization_id,
                BOQ.project_id == project_id,
                BOQ.status == BOQStatus.APPROVED,
                BOQItem.organization_id == context.organization_id,
                BOQItem.project_id == project_id,
            )
            .order_by(BOQ.code, BOQItem.line_number, BOQItem.id)
        )
    ).all()

    return [
        BOQFieldReferenceRead(
            item_id=item.id,
            boq_id=boq.id,
            boq_code=boq.code,
            boq_name=boq.name,
            boq_revision=boq.revision,
            wbs_code_id=item.wbs_code_id,
            line_number=item.line_number,
            item_code=item.item_code,
            description=item.description,
            unit_code=item.unit_code,
            quantity=item.quantity,
            item_revision=item.revision,
        )
        for item, boq in rows
    ]
