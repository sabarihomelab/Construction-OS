from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.configuration.router import router as configuration_router
from app.modules.events.router import router as realtime_router
from app.modules.field.router import router as field_router
from app.modules.health.router import router as health_router
from app.modules.offline.router import router as offline_router
from app.modules.projects.router import router as projects_router
from app.modules.rfis.router import router as rfis_router
from app.modules.search.bootstrap import register_builtin_search_providers
from app.modules.sessions.router import router as session_router
from app.modules.submittals.router import router as submittals_router


def create_app() -> FastAPI:
    settings = get_settings()
    register_builtin_search_providers()
    application = FastAPI(title=settings.app_name, version="0.10.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(session_router, prefix="/api/v1")
    application.include_router(realtime_router, prefix="/api/v1")
    application.include_router(offline_router, prefix="/api/v1")
    application.include_router(configuration_router, prefix="/api/v1")
    application.include_router(projects_router, prefix="/api/v1")
    application.include_router(rfis_router, prefix="/api/v1")
    application.include_router(submittals_router, prefix="/api/v1")
    application.include_router(field_router, prefix="/api/v1")
    return application


app = create_app()
