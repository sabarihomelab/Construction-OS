from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class EmploymentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


class Employee(UUIDTimestampMixin, Base):
    __tablename__ = "employees"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    employee_number: Mapped[str] = mapped_column(String(64), index=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE
    )


class Crew(UUIDTimestampMixin, Base):
    __tablename__ = "crews"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    supervisor_employee_id: Mapped[UUID | None] = mapped_column(nullable=True)
