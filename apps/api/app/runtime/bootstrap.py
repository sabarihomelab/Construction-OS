from importlib import import_module

from fastapi import APIRouter, FastAPI

from app.runtime.deployment import RuntimePlan


def _load_router(import_path: str) -> APIRouter:
    module_name, attribute = import_path.split(":", maxsplit=1)
    module = import_module(module_name)
    router = getattr(module, attribute)
    if not isinstance(router, APIRouter):
        raise TypeError(f"Runtime router is not an APIRouter: {import_path}")
    return router


def register_runtime_search_providers(plan: RuntimePlan) -> None:
    for manifest in plan.modules:
        if manifest.search_provider_module:
            import_module(manifest.search_provider_module)


def mount_runtime_routers(application: FastAPI, plan: RuntimePlan) -> None:
    for manifest in plan.modules:
        if manifest.api_router:
            application.include_router(_load_router(manifest.api_router), prefix="/api/v1")
