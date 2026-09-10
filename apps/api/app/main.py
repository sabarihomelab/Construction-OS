from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.configuration.router import router as configuration_router
from app.modules.events.router import router as realtime_router
from app.modules.health.router import router as health_router
from app.modules.offline.router import router as offline_router
from app.modules.projects.router import router as projects_router
from app.modules.rfis.router import router as rfis_router
from app.modules.sessions.router import router as session_router
from app.modules.submittals.router import router as submittals_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.9.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(session_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")
app.include_router(offline_router, prefix="/api/v1")
app.include_router(configuration_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(rfis_router, prefix="/api/v1")
app.include_router(submittals_router, prefix="/api/v1")
