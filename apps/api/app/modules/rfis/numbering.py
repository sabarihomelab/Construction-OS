from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RFIProjectCounter(Base):
    __tablename__ = "rfi_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_rfi_project_counters_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", name="uq_rfi_project_counters_project"),
        CheckConstraint("next_number >= 1", name="ck_rfi_project_counters_next_number"),
    )

    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    next_number: Mapped[int] = mapped_column(default=1)


async def allocate_rfi_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> int:
    counter = await db.scalar(
        select(RFIProjectCounter)
        .where(
            RFIProjectCounter.project_id == project_id,
            RFIProjectCounter.organization_id == organization_id,
        )
        .with_for_update()
    )
    if counter is None:
        counter = RFIProjectCounter(
            project_id=project_id,
            organization_id=organization_id,
            next_number=2,
        )
        db.add(counter)
        await db.flush()
        return 1
    number = counter.next_number
    counter.next_number += 1
    await db.flush()
    return number
