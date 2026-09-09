from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.workforce.models import Crew, Employee
from app.modules.workforce.schemas import CrewCreate, CrewRead, EmployeeCreate, EmployeeRead

router = APIRouter(prefix="/workforce", tags=["workforce"])


@router.get("/employees", response_model=list[EmployeeRead])
async def list_employees(db: DbSession):
    result = await db.execute(select(Employee).order_by(Employee.last_name, Employee.first_name))
    return list(result.scalars())


@router.post("/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreate, db: DbSession):
    employee = Employee(**payload.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get("/crews", response_model=list[CrewRead])
async def list_crews(db: DbSession):
    result = await db.execute(select(Crew).order_by(Crew.name))
    return list(result.scalars())


@router.post("/crews", response_model=CrewRead, status_code=status.HTTP_201_CREATED)
async def create_crew(payload: CrewCreate, db: DbSession):
    crew = Crew(**payload.model_dump())
    db.add(crew)
    await db.commit()
    await db.refresh(crew)
    return crew
