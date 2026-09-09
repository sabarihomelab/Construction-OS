from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.field.router import router as field_router
from app.modules.health.router import router as health_router
from app.modules.organizations.router import router as organizations_router
from app.modules.projects.router import router as projects_router
from app.modules.workforce.router import router as workforce_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(workforce_router, prefix="/api/v1")
app.include_router(field_router, prefix="/api/v1")
