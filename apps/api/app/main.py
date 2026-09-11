from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.authentication.bootstrap import configure_authentication_providers
from app.modules.authentication.native_router import router as native_authentication_router
from app.modules.configuration.router import router as configuration_router
from app.modules.events.router import router as realtime_router
from app.modules.health.router import router as health_router
from app.modules.help.router import router as help_router
from app.modules.offline.router import router as offline_router
from app.modules.organizations.router import router as organization_router
from app.modules.sessions.router import router as session_router
from app.runtime.bootstrap import mount_runtime_routers, register_runtime_search_providers
from app.runtime.deployment import build_runtime_plan


def create_app() -> FastAPI:
    settings = get_settings()
    configure_authentication_providers(settings)
    runtime_plan = build_runtime_plan(settings)
    register_runtime_search_providers(runtime_plan)

    application = FastAPI(title=settings.app_name, version="0.12.0")
    application.state.runtime_plan = runtime_plan

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(native_authentication_router, prefix="/api/v1")
    application.include_router(session_router, prefix="/api/v1")
    application.include_router(realtime_router, prefix="/api/v1")
    application.include_router(offline_router, prefix="/api/v1")
    application.include_router(configuration_router, prefix="/api/v1")
    application.include_router(organization_router, prefix="/api/v1")
    application.include_router(help_router, prefix="/api/v1")
    mount_runtime_routers(application, runtime_plan)
    return application


app = create_app()
