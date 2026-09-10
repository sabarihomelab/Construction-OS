import pytest

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.search.providers import SearchProjectionProviderRegistry
from app.modules.search.schemas import SearchProjection
from app.modules.search.service import SearchValidationError, _validate_projection


def test_search_projection_table_is_registered() -> None:
    table = Base.metadata.tables["search_documents"]
    assert "search_vector" in table.c
    assert "required_permission_key" in table.c
    assert "scope_type" in table.c
    assert "scope_id" in table.c
    assert "entity_version" in table.c


def test_search_projection_is_tenant_owned() -> None:
    table = Base.metadata.tables["search_documents"]
    assert not table.c.organization_id.nullable
    unique_names = {constraint.name for constraint in table.constraints}
    assert "uq_search_documents_org_entity" in unique_names


def test_search_vector_has_gin_index() -> None:
    table = Base.metadata.tables["search_documents"]
    index = next(item for item in table.indexes if item.name == "ix_search_documents_vector")
    assert index.dialect_options["postgresql"]["using"] == "gin"


def test_projection_requires_complete_scope_pair() -> None:
    projection = SearchProjection(
        entity_type="rfi",
        entity_id="123",
        title="RFI 123",
        scope_type="project",
    )
    with pytest.raises(SearchValidationError, match="scope_type"):
        _validate_projection(projection)


def test_projection_route_hint_must_be_internal() -> None:
    projection = SearchProjection(
        entity_type="rfi",
        entity_id="123",
        title="RFI 123",
        route_hint="https://example.com/rfi/123",
    )
    with pytest.raises(SearchValidationError, match="internal"):
        _validate_projection(projection)


def test_projection_provider_registry_rejects_duplicate_entity_type() -> None:
    async def provider(_db, _organization_id, _entity_id):
        return None

    registry = SearchProjectionProviderRegistry()
    registry.register("rfi", provider)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("rfi", provider)


def test_projection_provider_registry_is_deterministic() -> None:
    async def provider(_db, _organization_id, _entity_id):
        return None

    registry = SearchProjectionProviderRegistry()
    registry.register("submittal", provider)
    registry.register("rfi", provider)
    assert registry.registered_entity_types() == ("rfi", "submittal")
