from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.organizations.models import Organization
from app.modules.organizations.schemas import OrganizationCreate, OrganizationRead

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
async def list_organizations(db: DbSession):
    result = await db.execute(select(Organization).order_by(Organization.name))
    return list(result.scalars())


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(payload: OrganizationCreate, db: DbSession):
    organization = Organization(**payload.model_dump())
    db.add(organization)
    await db.commit()
    await db.refresh(organization)
    return organization
