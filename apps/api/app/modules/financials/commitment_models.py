from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ProjectCommitmentAllocation(UUIDTimestampMixin, Base):
    __tablename__ = "project_commitment_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["commitment_id", "project_id", "organization_id"],
            [
                "project_commitments.id",
                "project_commitments.project_id",
                "project_commitments.organization_id",
            ],
            name="fk_project_commitment_allocations_commitment_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_line_id", "project_id", "organization_id"],
            [
                "purchase_order_lines.id",
                "purchase_order_lines.project_id",
                "purchase_order_lines.organization_id",
            ],
            name="fk_project_commitment_allocations_po_line_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_project_commitment_allocations_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_project_commitment_allocations_boq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_project_commitment_allocations_material_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "commitment_id",
            "line_number",
            name="uq_project_commitment_allocations_line",
        ),
        UniqueConstraint(
            "commitment_id",
            "source_line_id",
            name="uq_project_commitment_allocations_source_line",
        ),
        CheckConstraint("quantity > 0", name="ck_project_commitment_allocations_quantity"),
        CheckConstraint(
            "committed_amount >= 0",
            name="ck_project_commitment_allocations_committed_amount",
        ),
        CheckConstraint("tax_amount >= 0", name="ck_project_commitment_allocations_tax_amount"),
        CheckConstraint("gross_amount >= 0", name="ck_project_commitment_allocations_gross_amount"),
        CheckConstraint(
            "gross_amount = committed_amount + tax_amount",
            name="ck_project_commitment_allocations_amount_reconciliation",
        ),
        Index(
            "ix_project_commitment_allocations_project_wbs",
            "project_id",
            "wbs_code_id",
        ),
        Index(
            "ix_project_commitment_allocations_project_material",
            "project_id",
            "material_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    commitment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    source_line_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_code: Mapped[str] = mapped_column(String(40))
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
