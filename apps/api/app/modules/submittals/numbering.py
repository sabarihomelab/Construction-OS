from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SubmittalProjectCounter(Base):
    __tablename__ = "submittal_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_submittal_project_counters_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", name="uq_submittal_project_counters_project"),
        CheckConstraint(
            "next_number >= 1",
            name="ck_submittal_project_counters_next_number",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    next_number: Mapped[int] = mapped_column(default=1)


async def allocate_submittal_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> int:
    statement = (
        insert(SubmittalProjectCounter)
        .values(
            project_id=project_id,
            organization_id=organization_id,
            next_number=2,
        )
        .on_conflict_do_update(
            index_elements=[SubmittalProjectCounter.project_id],
            set_={"next_number": SubmittalProjectCounter.next_number + 1},
            where=SubmittalProjectCounter.organization_id == organization_id,
        )
        .returning(SubmittalProjectCounter.next_number)
    )
    next_number = await db.scalar(statement)
    if next_number is None:
        raise ValueError("Submittal numbering counter does not belong to this organization")
    return next_number - 1
