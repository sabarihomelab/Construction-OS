from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rfis.models import RFI, RFIResponse, RFIResponseStatus
from app.modules.search.schemas import SearchProjection


async def rfi_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        rfi_id = UUID(entity_id)
    except ValueError:
        return None

    rfi = await db.scalar(
        select(RFI).where(
            RFI.id == rfi_id,
            RFI.organization_id == organization_id,
        )
    )
    if rfi is None:
        return None

    official_response = await db.scalar(
        select(RFIResponse.response_text)
        .where(
            RFIResponse.rfi_id == rfi.id,
            RFIResponse.organization_id == organization_id,
            RFIResponse.status == RFIResponseStatus.OFFICIAL,
        )
        .order_by(RFIResponse.sequence.desc())
        .limit(1)
    )
    body_parts = [rfi.question]
    if official_response:
        body_parts.append(official_response)

    keywords = [f"RFI {rfi.number}", rfi.subject, rfi.status.value]
    if rfi.priority:
        keywords.append(rfi.priority)

    return SearchProjection(
        entity_type="rfi",
        entity_id=str(rfi.id),
        entity_version=rfi.version,
        required_permission_key="rfis.rfi.view",
        scope_type="project",
        scope_id=str(rfi.project_id),
        title=rfi.subject,
        subtitle=f"RFI {rfi.number} · {rfi.status.value}",
        body="\n".join(body_parts),
        keywords=keywords,
        route_hint=f"/projects/{rfi.project_id}/rfis/{rfi.id}",
        source_updated_at=rfi.updated_at,
    )
