from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class DPRWorkProgressEntry(UUIDTimestampMixin, Base):
    __tablename__ = "dpr_work_progress_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "project_id", "organization_id"],
            ["daily_reports.id", "daily_reports.project_id", "daily_reports.organization_id"],
            name="fk_dpr_work_progress_report_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_dpr_work_progress_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_dpr_work_progress_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_dpr_work_progress_id_org"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_dpr_work_progress_quantity"),
        Index("ix_dpr_work_progress_report", "daily_report_id", "created_at"),
        Index("ix_dpr_work_progress_project_wbs", "project_id", "wbs_code_id"),
        Index("ix_dpr_work_progress_project_boq", "project_id", "boq_item_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
