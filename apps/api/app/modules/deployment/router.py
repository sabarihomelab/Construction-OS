from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import DbSession
from app.modules.organizations.models import Organization

router = APIRouter(prefix="/deployment", tags=["deployment"])


class DeploymentOrganization(BaseModel):
    id: UUID
    name: str
    slug: str


class DeploymentBootstrapResponse(BaseModel):
    deployment_id: str
    dedicated_company: bool
    organization: DeploymentOrganization | None
    environment: str
    environment_name: str
    api_path: str = "/api/v1/"


@router.get("/bootstrap", response_model=DeploymentBootstrapResponse)
async def get_deployment_bootstrap(db: DbSession) -> DeploymentBootstrapResponse:
    settings = get_settings()
    organization: Organization | None = None

    if settings.deployment_organization_id is not None:
        organization = await db.get(Organization, settings.deployment_organization_id)
        if organization is None or not organization.is_active:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Deployment company binding is unavailable",
            )

    return DeploymentBootstrapResponse(
        deployment_id=settings.deployment_id,
        dedicated_company=organization is not None,
        organization=(
            DeploymentOrganization(
                id=organization.id,
                name=organization.name,
                slug=organization.slug,
            )
            if organization is not None
            else None
        ),
        environment=settings.environment,
        environment_name=settings.environment_name,
    )
