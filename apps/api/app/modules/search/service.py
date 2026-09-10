from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.service import enqueue_job
from app.modules.search.models import SearchDocument
from app.modules.search.schemas import SearchProjection, SearchResult


class SearchValidationError(ValueError):
    pass


def _validate_projection(projection: SearchProjection) -> None:
    if (projection.scope_type is None) != (projection.scope_id is None):
        raise SearchValidationError("scope_type and scope_id must be supplied together")
    if projection.route_hint is not None and not projection.route_hint.startswith("/"):
        raise SearchValidationError("route_hint must be an internal application path")


def _keywords_text(keywords: list[str]) -> str:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in keywords:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value[:200])
    return " ".join(normalized)


async def upsert_search_document(
    db: AsyncSession,
    *,
    organization_id: UUID,
    projection: SearchProjection,
    indexed_at: datetime | None = None,
) -> SearchDocument:
    _validate_projection(projection)
    document = await db.scalar(
        select(SearchDocument)
        .where(
            SearchDocument.organization_id == organization_id,
            SearchDocument.entity_type == projection.entity_type,
            SearchDocument.entity_id == projection.entity_id,
        )
        .with_for_update()
    )

    if (
        document is not None
        and document.entity_version is not None
        and projection.entity_version is not None
        and document.entity_version > projection.entity_version
    ):
        return document

    values = {
        "entity_version": projection.entity_version,
        "required_permission_key": projection.required_permission_key,
        "scope_type": projection.scope_type,
        "scope_id": projection.scope_id,
        "title": projection.title.strip(),
        "subtitle": projection.subtitle.strip() if projection.subtitle else None,
        "body": projection.body.strip(),
        "keywords_text": _keywords_text(projection.keywords),
        "route_hint": projection.route_hint,
        "source_updated_at": projection.source_updated_at,
        "indexed_at": indexed_at or datetime.now(UTC),
    }
    if document is None:
        document = SearchDocument(
            organization_id=organization_id,
            entity_type=projection.entity_type,
            entity_id=projection.entity_id,
            **values,
        )
        db.add(document)
    else:
        for key, value in values.items():
            setattr(document, key, value)

    await db.flush()
    return document


async def remove_search_document(
    db: AsyncSession,
    *,
    organization_id: UUID,
    entity_type: str,
    entity_id: str,
    entity_version: int | None = None,
) -> bool:
    document = await db.scalar(
        select(SearchDocument)
        .where(
            SearchDocument.organization_id == organization_id,
            SearchDocument.entity_type == entity_type,
            SearchDocument.entity_id == entity_id,
        )
        .with_for_update()
    )
    if document is None:
        return False
    if (
        entity_version is not None
        and document.entity_version is not None
        and document.entity_version > entity_version
    ):
        return False
    await db.delete(document)
    await db.flush()
    return True


async def schedule_search_index(
    db: AsyncSession,
    *,
    organization_id: UUID,
    entity_type: str,
    entity_id: str | UUID,
    entity_version: int | None = None,
    correlation_id: UUID | None = None,
) -> None:
    version_key = entity_version if entity_version is not None else "current"
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="search.index_entity",
        idempotency_key=f"search:{entity_type}:{entity_id}:v:{version_key}",
        payload={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_version": entity_version,
        },
        correlation_id=correlation_id,
    )


async def schedule_search_delete(
    db: AsyncSession,
    *,
    organization_id: UUID,
    entity_type: str,
    entity_id: str | UUID,
    entity_version: int | None = None,
    correlation_id: UUID | None = None,
) -> None:
    version_key = entity_version if entity_version is not None else "current"
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="search.delete_entity",
        idempotency_key=f"search-delete:{entity_type}:{entity_id}:v:{version_key}",
        payload={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_version": entity_version,
        },
        correlation_id=correlation_id,
    )


def _scope_filter(allowed_scopes: Mapping[str, set[str]] | None):
    if not allowed_scopes:
        return SearchDocument.scope_type.is_(None)

    scope_conditions = [SearchDocument.scope_type.is_(None)]
    for scope_type, scope_ids in allowed_scopes.items():
        if "*" in scope_ids:
            scope_conditions.append(SearchDocument.scope_type == scope_type)
        elif scope_ids:
            scope_conditions.append(
                and_(
                    SearchDocument.scope_type == scope_type,
                    SearchDocument.scope_id.in_(scope_ids),
                )
            )
    return or_(*scope_conditions)


def _permission_filter(
    permission_keys: set[str],
    scoped_permissions: Mapping[str, Mapping[str, set[str]]] | None,
):
    permission_conditions = [SearchDocument.required_permission_key.is_(None)]
    if permission_keys:
        permission_conditions.append(SearchDocument.required_permission_key.in_(permission_keys))

    if scoped_permissions:
        for scope_type, by_scope_id in scoped_permissions.items():
            for scope_id, scope_permission_keys in by_scope_id.items():
                if not scope_permission_keys:
                    continue
                permission_conditions.append(
                    and_(
                        SearchDocument.scope_type == scope_type,
                        SearchDocument.scope_id == scope_id,
                        SearchDocument.required_permission_key.in_(scope_permission_keys),
                    )
                )
    return or_(*permission_conditions)


async def search_documents(
    db: AsyncSession,
    *,
    organization_id: UUID,
    query: str,
    permission_keys: set[str],
    allowed_scopes: Mapping[str, set[str]] | None = None,
    scoped_permissions: Mapping[str, Mapping[str, set[str]]] | None = None,
    entity_types: set[str] | None = None,
    limit: int = 30,
) -> list[SearchResult]:
    normalized_query = " ".join(query.split())
    if len(normalized_query) < 2:
        raise SearchValidationError("Search query must contain at least 2 characters")
    if len(normalized_query) > 300:
        raise SearchValidationError("Search query is too long")
    if limit < 1 or limit > 100:
        raise SearchValidationError("Search limit must be between 1 and 100")

    ts_query = func.websearch_to_tsquery("simple", normalized_query)
    rank = func.ts_rank_cd(SearchDocument.search_vector, ts_query)

    statement = select(SearchDocument, rank.label("rank")).where(
        SearchDocument.organization_id == organization_id,
        SearchDocument.search_vector.op("@@")(ts_query),
        _permission_filter(permission_keys, scoped_permissions),
        _scope_filter(allowed_scopes),
    )
    if entity_types:
        statement = statement.where(SearchDocument.entity_type.in_(entity_types))

    rows = (
        await db.execute(
            statement.order_by(rank.desc(), SearchDocument.title, SearchDocument.id).limit(limit)
        )
    ).all()
    return [
        SearchResult(
            entity_type=document.entity_type,
            entity_id=document.entity_id,
            entity_version=document.entity_version,
            title=document.title,
            subtitle=document.subtitle,
            route_hint=document.route_hint,
            rank=float(score or 0),
        )
        for document, score in rows
    ]


async def purge_search_documents_for_tenant(db: AsyncSession, organization_id: UUID) -> int:
    result = await db.execute(
        delete(SearchDocument).where(SearchDocument.organization_id == organization_id)
    )
    return result.rowcount or 0
