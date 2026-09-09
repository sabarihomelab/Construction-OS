from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class Project(UUIDTimestampMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    number: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.PLANNING)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
