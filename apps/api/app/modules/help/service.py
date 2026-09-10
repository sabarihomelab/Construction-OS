from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.help.models import TenantKnowledgeChunk, TenantKnowledgeSource
from app.modules.jobs.service import enqueue_job


class HelpValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProductHelpTopic:
    key: str
    title: str
    route_prefix: str
    document_path: str
    required_permission_key: str | None = None
    feature_key: str | None = None


class ProductHelpRegistry:
    def __init__(self) -> None:
        self._topics: dict[str, ProductHelpTopic] = {}

    def register(self, topic: ProductHelpTopic) -> None:
        if not topic.key.strip() or not topic.route_prefix.startswith("/"):
            raise ValueError("Help topic requires key and absolute route prefix")
        if topic.key in self._topics:
            raise ValueError(f"Help topic already registered: {topic.key}")
        self._topics[topic.key] = topic

    def for_route(self, route: str, permission_keys: set[str]) -> tuple[ProductHelpTopic, ...]:
        matches = [
            topic
            for topic in self._topics.values()
            if route.startswith(topic.route_prefix)
            and (
                topic.required_permission_key is None
                or topic.required_permission_key in permission_keys
            )
        ]
        return tuple(sorted(matches, key=lambda topic: len(topic.route_prefix), reverse=True))


def knowledge_source_is_visible(
    source: TenantKnowledgeSource,
    *,
    permission_keys: set[str],
    allowed_scopes: Mapping[str, set[str]] | None = None,
) -> bool:
    if source.required_permission_key and source.required_permission_key not in permission_keys:
        return False
    if source.scope_type is None:
        return source.scope_id is None
    if source.scope_id is None or allowed_scopes is None:
        return False
    allowed = allowed_scopes.get(source.scope_type, set())
    return "*" in allowed or source.scope_id in allowed


async def queue_knowledge_reindex(
    db: AsyncSession,
    *,
    organization_id: UUID,
    source_id: UUID,
    source_version: int,
    actor_user_id: UUID | None = None,
) -> None:
    if source_version < 1:
        raise HelpValidationError("Knowledge source version must be at least 1")
    source = await db.scalar(
        select(TenantKnowledgeSource).where(
            TenantKnowledgeSource.id == source_id,
            TenantKnowledgeSource.organization_id == organization_id,
        )
    )
    if source is None:
        raise HelpValidationError("Knowledge source was not found")
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="help.index_source",
        payload={"source_id": str(source_id), "source_version": source_version},
        idempotency_key=f"help.index_source:{source_id}:{source_version}",
        created_by_user_id=actor_user_id,
    )


async def visible_knowledge_chunks(
    db: AsyncSession,
    *,
    organization_id: UUID,
    permission_keys: set[str],
    allowed_scopes: Mapping[str, set[str]] | None = None,
    limit: int = 100,
) -> list[TenantKnowledgeChunk]:
    if limit < 1 or limit > 500:
        raise HelpValidationError("Knowledge chunk limit must be between 1 and 500")
    sources = list(
        (
            await db.scalars(
                select(TenantKnowledgeSource).where(
                    TenantKnowledgeSource.organization_id == organization_id,
                    TenantKnowledgeSource.status == "ready",
                )
            )
        ).all()
    )
    visible_source_ids = [
        source.id
        for source in sources
        if knowledge_source_is_visible(
            source,
            permission_keys=permission_keys,
            allowed_scopes=allowed_scopes,
        )
    ]
    if not visible_source_ids:
        return []
    chunks = await db.scalars(
        select(TenantKnowledgeChunk)
        .where(
            TenantKnowledgeChunk.organization_id == organization_id,
            TenantKnowledgeChunk.source_id.in_(visible_source_ids),
        )
        .order_by(TenantKnowledgeChunk.source_id, TenantKnowledgeChunk.ordinal)
        .limit(limit)
    )
    return list(chunks.all())
