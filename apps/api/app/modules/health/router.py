from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.config import get_settings
from app.core.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "construction-os-api"}


@router.get("/health/ready")
async def readiness(request: Request, db: DbSession) -> dict[str, object]:
    await db.execute(text("SELECT 1"))
    settings = get_settings()
    plan = request.app.state.runtime_plan
    return {
        "status": "ready",
        "service": "construction-os-api",
        "environment": settings.environment,
        "environment_name": settings.environment_name,
        "product_market": settings.product_market,
        "deployment_profile": plan.profile.value,
        "database_mode": plan.database_mode.value,
        "storage_provider": plan.storage_provider,
        "runtime_modules": sorted(plan.module_keys),
        "worker_profiles": list(plan.worker_profiles),
        "assistant": {
            "enabled": settings.ai_assistant_enabled,
            "provider": settings.ai_provider,
            "model": settings.ai_model or None,
        },
    }
