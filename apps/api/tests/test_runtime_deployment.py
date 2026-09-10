from fastapi import FastAPI

from app.core.config import Settings
from app.modules.features.service import resolve_visible_features
from app.modules.jobs.handlers import JobHandlerRegistry
from app.runtime.bootstrap import mount_runtime_routers
from app.runtime.deployment import build_runtime_plan
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
    paths = {route.path for route in application.routes if hasattr(route, "path")}
    assert "/api/v1/projects" in paths
    assert not any("/rfis" in path for path in paths)
    assert not any("/daily-reports" in path for path in paths)


def test_feature_visibility_requires_deployment_availability() -> None:
    visible = resolve_visible_features(
        {"projects.project.view", "field.daily_report.view"},
        allow_preview=True,
        deployment_modules={"projects"},
    )
    keys = {feature.key for feature in visible}
    assert "projects" in keys
    assert "field" not in keys


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
