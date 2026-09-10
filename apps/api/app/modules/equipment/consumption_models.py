from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
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


class MaterialConsumptionStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class MaterialConsumption(UUIDTimestampMixin, Base):
    __tablename__ = "material_consumptions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_material_consumptions_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_material_consumptions_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_material_consumptions_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_material_consumptions_boq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_consumptions_creator_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "posted_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_consumptions_poster_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "reversed_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_consumptions_reverser_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_material_consumptions_scope"
        ),
        CheckConstraint("quantity > 0", name="ck_material_consumptions_quantity"),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_material_consumptions_unit_cost",
        ),
        CheckConstraint(
            "total_cost IS NULL OR total_cost >= 0",
            name="ck_material_consumptions_total_cost",
        ),
        CheckConstraint("revision >= 1", name="ck_material_consumptions_revision"),
        Index(
            "ix_material_consumptions_project_date",
            "project_id",
            "consumption_date",
        ),
        Index(
            "ix_material_consumptions_project_material",
            "project_id",
            "material_id",
        ),
        Index(
            "ix_material_consumptions_project_status",
            "project_id",
            "status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    material_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    consumption_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_code: Mapped[str] = mapped_column(String(40))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    cost_basis: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MaterialConsumptionStatus] = mapped_column(
        Enum(MaterialConsumptionStatus, native_enum=False, values_callable=enum_values),
        default=MaterialConsumptionStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    created_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    posted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
