from dataclasses import replace

from fastapi import FastAPI

from app.core.config import Settings
from app.modules.features import service as feature_service
from app.modules.features.registry import FEATURE_REGISTRY, FEATURES_BY_KEY, FeatureReleaseState
from app.modules.jobs.handlers import JobHandlerRegistry
from app.runtime.bootstrap import mount_runtime_routers
from app.runtime.deployment import build_runtime_plan
from app.runtime.installer_cli import module_catalog, resolved_module_keys
from app.runtime.modules import ModuleSelectionError, resolve_runtime_modules


async def _job_handler(_db, _job):
    return None


def test_lightweight_rfi_selection_only_resolves_hard_dependency() -> None:
    modules = resolve_runtime_modules("rfis")
    keys = {module.key for module in modules}
    assert keys == {"projects", "rfis"}


def test_drawing_selection_resolves_dependencies_and_heavy_profile() -> None:
    plan = build_runtime_plan(Settings(runtime_modules="drawings", worker_profiles="auto"))
    assert plan.module_keys == {"projects", "documents", "drawings"}
    assert set(plan.worker_profiles) == {"general", "drawings"}


def test_unknown_runtime_module_fails_closed() -> None:
    try:
        resolve_runtime_modules("projects,not-a-module")
    except ModuleSelectionError as exc:
        assert "not-a-module" in str(exc)
    else:
        raise AssertionError("Unknown runtime modules must be rejected")


def test_runtime_router_mounting_excludes_unselected_modules() -> None:
    plan = build_runtime_plan(Settings(runtime_modules="projects", worker_profiles="general"))
    application = FastAPI()
    mount_runtime_routers(application, plan)
    paths = set(application.openapi()["paths"])
    assert "/api/v1/projects" in paths
    assert not any("/rfis" in path for path in paths)
    assert not any("/daily-reports" in path for path in paths)


def test_feature_visibility_requires_deployment_availability(monkeypatch) -> None:
    projects = replace(
        FEATURES_BY_KEY["projects"],
        release_state=FeatureReleaseState.AVAILABLE,
    )
    registry = tuple(projects if feature.key == "projects" else feature for feature in FEATURE_REGISTRY)
    by_key = {feature.key: feature for feature in registry}
    monkeypatch.setattr(feature_service, "FEATURE_REGISTRY", registry)
    monkeypatch.setattr(feature_service, "FEATURES_BY_KEY", by_key)

    visible = feature_service.resolve_visible_features(
        {"projects.project.view"},
        deployment_modules={"projects"},
    )
    assert "projects" in {feature.key for feature in visible}

    hidden = feature_service.resolve_visible_features(
        {"projects.project.view"},
        deployment_modules=set(),
    )
    assert "projects" not in {feature.key for feature in hidden}


def test_worker_registry_filters_by_profile_and_module() -> None:
    jobs = JobHandlerRegistry()
    jobs.register("shared.cleanup", _job_handler)
    jobs.register(
        "drawings.render",
        _job_handler,
        profile="drawings",
        module_key="drawings",
    )

    assert jobs.enabled_job_types(
        worker_profiles={"general"},
        module_keys={"projects", "rfis"},
    ) == ("shared.cleanup",)
    assert jobs.enabled_job_types(
        worker_profiles={"general", "drawings"},
        module_keys={"projects", "documents", "drawings"},
    ) == ("drawings.render", "shared.cleanup")


def test_external_database_profile_does_not_change_application_contract() -> None:
    settings = Settings(
        deployment_profile="split",
        database_mode="external",
        database_url="postgresql+asyncpg://app:secret@db.internal:5432/construction_os",
        runtime_modules="projects,field",
        storage_provider="s3-compatible",
    )
    plan = build_runtime_plan(settings)
    assert plan.profile.value == "split"
    assert plan.database_mode.value == "external"
    assert plan.storage_provider == "s3-compatible"
    assert plan.module_keys == {"projects", "field"}


def test_installer_catalog_uses_runtime_manifest() -> None:
    catalog_keys = {item["key"] for item in module_catalog()}
    runtime_keys = {module.key for module in resolve_runtime_modules("*")}
    assert catalog_keys == runtime_keys


def test_installer_dependency_resolution_matches_runtime() -> None:
    assert resolved_module_keys("drawings") == ["projects", "documents", "drawings"]
    assert resolved_module_keys("rfis") == ["projects", "rfis"]
