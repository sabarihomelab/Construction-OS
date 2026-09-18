from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.schemas import SearchProjection

SearchProjectionProvider = Callable[
    [AsyncSession, UUID, str], Awaitable[SearchProjection | None]
]


class SearchProjectionProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SearchProjectionProvider] = {}

    def register(self, entity_type: str, provider: SearchProjectionProvider) -> None:
        normalized = entity_type.strip()
        if not normalized:
            raise ValueError("entity_type is required")
        if normalized in self._providers:
            raise ValueError(f"Search provider already registered: {normalized}")
        self._providers[normalized] = provider

    def get(self, entity_type: str) -> SearchProjectionProvider:
        try:
            return self._providers[entity_type]
        except KeyError as exc:
            raise KeyError(f"No search provider registered for {entity_type}") from exc

    def contains(self, entity_type: str) -> bool:
        return entity_type in self._providers

    def registered_entity_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


search_projection_providers = SearchProjectionProviderRegistry()
