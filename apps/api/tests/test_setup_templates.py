from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.setup.service import TemplateProvider, TemplateProviderRegistry


def test_setup_tables_are_registered() -> None:
    expected = {
        "configuration_templates",
        "configuration_template_versions",
        "setup_runs",
        "configuration_health_checks",
    }
    assert expected.issubset(Base.metadata.tables)


def test_setup_permissions_are_atomic() -> None:
    assert "admin.setup.view" in PERMISSIONS_BY_KEY
    assert "admin.setup.manage" in PERMISSIONS_BY_KEY


def test_template_versions_preserve_history() -> None:
    table = Base.metadata.tables["configuration_template_versions"]
    assert "version" in table.c
    assert "status" in table.c
    assert "payload" in table.c


def test_setup_runs_use_optimistic_revision_and_validation_state() -> None:
    table = Base.metadata.tables["setup_runs"]
    assert "revision" in table.c
    assert "validation_summary" in table.c
    assert "result_summary" in table.c


def test_template_provider_registry_rejects_duplicate_target() -> None:
    async def validate(*_args):
        raise AssertionError("not invoked")

    async def apply(*_args):
        raise AssertionError("not invoked")

    registry = TemplateProviderRegistry()
    provider = TemplateProvider(target_type="project", validate=validate, apply=apply)
    registry.register(provider)
    try:
        registry.register(provider)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Duplicate template provider must be rejected")
