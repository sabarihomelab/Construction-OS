from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drawings.models import DrawingSet, DrawingSheet
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def drawing_sheet_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        sheet_id = UUID(entity_id)
    except ValueError:
        return None

    row = (
        await db.execute(
            select(DrawingSheet, DrawingSet.project_id)
            .join(DrawingSet, DrawingSet.id == DrawingSheet.drawing_set_id)
            .where(
                DrawingSheet.id == sheet_id,
                DrawingSheet.organization_id == organization_id,
                DrawingSet.organization_id == organization_id,
            )
        )
    ).first()
    if row is None:
        return None
    sheet, project_id = row
    keywords = [sheet.sheet_number]
    if sheet.discipline_code:
        keywords.append(sheet.discipline_code)
    return SearchProjection(
        entity_type="drawing_sheet",
        entity_id=str(sheet.id),
        entity_version=sheet.version,
        required_permission_key="drawings.drawing.view",
        scope_type="project",
        scope_id=str(project_id),
        title=f"{sheet.sheet_number} — {sheet.title}",
        subtitle="Drawing",
        body="",
        keywords=keywords,
        route_hint=f"/projects/{project_id}/drawings/{sheet.id}",
        source_updated_at=sheet.updated_at,
    )


if not search_projection_providers.contains("drawing_sheet"):
    search_projection_providers.register("drawing_sheet", drawing_sheet_search_projection)
