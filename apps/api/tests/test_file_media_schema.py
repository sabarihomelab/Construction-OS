from sqlalchemy import BigInteger

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.files.storage import StorageProviderRegistry


def test_file_media_tables_are_registered() -> None:
    expected = {
        "storage_objects",
        "organization_storage_usage",
        "file_assets",
        "file_versions",
        "file_links",
        "file_variants",
        "upload_sessions",
    }
    assert expected.issubset(Base.metadata.tables)


def test_file_bytes_are_not_stored_in_transactional_tables() -> None:
    prohibited = {"data", "bytes", "blob", "content", "file_content"}
    for table_name in {
        "storage_objects",
        "file_assets",
        "file_versions",
        "file_variants",
        "upload_sessions",
    }:
        assert prohibited.isdisjoint(Base.metadata.tables[table_name].c.keys())


def test_storage_accounting_uses_bigint() -> None:
    usage = Base.metadata.tables["organization_storage_usage"]
    assert isinstance(usage.c.committed_bytes.type, BigInteger)
    assert isinstance(usage.c.reserved_bytes.type, BigInteger)
    assert isinstance(usage.c.object_count.type, BigInteger)


def test_storage_quota_is_optional_policy_not_required_ceiling() -> None:
    settings = Base.metadata.tables["organization_settings"]
    assert settings.c.storage_quota_bytes.nullable
    assert isinstance(settings.c.storage_quota_bytes.type, BigInteger)


def test_file_versions_have_tenant_consistent_asset_and_object_constraints() -> None:
    table = Base.metadata.tables["file_versions"]
    names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_file_versions_asset_org" in names
    assert "fk_file_versions_storage_object_org" in names


def test_file_links_pin_versions_with_tenant_identity() -> None:
    table = Base.metadata.tables["file_links"]
    names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_file_links_asset_org" in names
    assert "fk_file_links_pinned_version_org" in names


def test_file_variants_cannot_cross_tenants() -> None:
    table = Base.metadata.tables["file_variants"]
    names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_file_variants_file_version_org" in names
    assert "fk_file_variants_storage_object_org" in names


def test_file_permissions_are_atomic() -> None:
    expected = {
        "files.file.view",
        "files.file.download",
        "files.file.upload",
        "files.file.manage",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)


def test_storage_provider_registry_rejects_duplicate_key() -> None:
    class FakeProvider:
        provider_key = "test"

    registry = StorageProviderRegistry()
    provider = FakeProvider()
    registry.register(provider)  # type: ignore[arg-type]

    try:
        registry.register(provider)  # type: ignore[arg-type]
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Duplicate provider registration must be rejected")
