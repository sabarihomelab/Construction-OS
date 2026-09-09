from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(db: DbSession):
    result = await db.execute(select(Project).order_by(Project.name))
    return list(result.scalars())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, db: DbSession):
    project = Project(**payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project
