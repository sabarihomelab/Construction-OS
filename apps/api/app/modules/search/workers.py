from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.handlers import JobHandlerRegistry
from app.modules.jobs.models import BackgroundJob
from app.modules.search.bootstrap import register_builtin_search_providers
from app.modules.search.providers import SearchProjectionProviderRegistry
from app.modules.search.service import remove_search_document, upsert_search_document


class SearchJobError(ValueError):
    pass


def _payload_string(job: BackgroundJob, key: str) -> str:
    value = job.payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SearchJobError(f"Search job payload requires {key}")
    return value.strip()


def _payload_version(job: BackgroundJob) -> int | None:
    value = job.payload.get("entity_version")
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        raise SearchJobError("entity_version must be a positive integer when supplied")
    return value


def build_index_handler(providers: SearchProjectionProviderRegistry):
    async def index_entity(db: AsyncSession, job: BackgroundJob) -> dict[str, object]:
        entity_type = _payload_string(job, "entity_type")
        entity_id = _payload_string(job, "entity_id")
        requested_version = _payload_version(job)
        provider = providers.get(entity_type)
        projection = await provider(db, job.organization_id, entity_id)
        if projection is None:
            removed = await remove_search_document(
                db,
                organization_id=job.organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_version=requested_version,
            )
            return {"indexed": False, "removed": removed}
        if projection.entity_type != entity_type or projection.entity_id != entity_id:
            raise SearchJobError("Search provider returned a different entity identity")
        if (
            requested_version is not None
            and projection.entity_version is not None
            and projection.entity_version < requested_version
        ):
            raise SearchJobError("Search provider returned an older entity version")

        document = await upsert_search_document(
            db,
            organization_id=job.organization_id,
            projection=projection,
        )
        return {
            "indexed": True,
            "entity_type": document.entity_type,
            "entity_id": document.entity_id,
            "entity_version": document.entity_version,
        }

    return index_entity


def build_delete_handler():
    async def delete_entity(db: AsyncSession, job: BackgroundJob) -> dict[str, object]:
        entity_type = _payload_string(job, "entity_type")
        entity_id = _payload_string(job, "entity_id")
        entity_version = _payload_version(job)
        removed = await remove_search_document(
            db,
            organization_id=job.organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_version=entity_version,
        )
        return {"removed": removed, "entity_type": entity_type, "entity_id": entity_id}

    return delete_entity


def register_search_handlers(
    jobs: JobHandlerRegistry,
    providers: SearchProjectionProviderRegistry,
) -> None:
    register_builtin_search_providers()
    jobs.register("search.index_entity", build_index_handler(providers), timeout_seconds=120)
    jobs.register("search.delete_entity", build_delete_handler(), timeout_seconds=60)
