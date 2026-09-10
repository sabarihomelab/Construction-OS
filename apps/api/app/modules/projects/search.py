from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.models import Project
from app.modules.search.schemas import SearchProjection


async def project_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        project_id = UUID(entity_id)
    except ValueError:
        return None

    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        return None

    address_parts = [
        project.address_line_1,
        project.address_line_2,
        project.locality,
        project.region,
        project.postal_code,
        project.country_code,
    ]
    address_text = ", ".join(part for part in address_parts if part)
    body_parts = [project.description or "", address_text]

    return SearchProjection(
        entity_type="project",
        entity_id=str(project.id),
        entity_version=project.revision,
        required_permission_key="projects.project.view",
        scope_type="project",
        scope_id=str(project.id),
        title=project.name,
        subtitle=project.number,
        body="\n".join(part for part in body_parts if part),
        keywords=[project.number, project.name, project.status.value],
        route_hint=f"/projects/{project.id}",
        source_updated_at=project.updated_at,
    )
