from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def project_document_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        document_id = UUID(entity_id)
    except ValueError:
        return None

    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )
    if document is None:
        return None

    keywords = [document.number, document.kind.value]
    if document.discipline_code:
        keywords.append(document.discipline_code)

    return SearchProjection(
        entity_type="document",
        entity_id=str(document.id),
        entity_version=document.version,
        required_permission_key="documents.document.view",
        scope_type="project",
        scope_id=str(document.project_id),
        title=f"{document.number} — {document.title}",
        subtitle=document.kind.value.replace("_", " ").title(),
        body=document.description or "",
        keywords=keywords,
        route_hint=f"/projects/{document.project_id}/documents/{document.id}",
        source_updated_at=document.updated_at,
    )


if not search_projection_providers.contains("document"):
    search_projection_providers.register("document", project_document_search_projection)
