from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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


class StockLocationType(StrEnum):
    SITE_STORE = "site_store"
    WORK_AREA = "work_area"
    YARD = "yard"
    WAREHOUSE = "warehouse"
    OTHER = "other"


class StockLocationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class StockTransactionType(StrEnum):
    OPENING_BALANCE = "opening_balance"
    GRN_RECEIPT = "grn_receipt"
    ISSUE = "issue"
    CONSUMPTION = "consumption"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    RETURN_IN = "return_in"
    RETURN_OUT = "return_out"
    REJECTION = "rejection"
    WASTAGE = "wastage"
    DAMAGE = "damage"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"


class StockDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class StockSourceType(StrEnum):
    GOODS_RECEIPT = "goods_receipt"
    MATERIAL_CONSUMPTION = "material_consumption"
    MANUAL_ADJUSTMENT = "manual_adjustment"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class MaterialStockLocation(UUIDTimestampMixin, Base):
    __tablename__ = "material_stock_locations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_material_stock_locations_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "project_id",
            "code",
            name="uq_material_stock_locations_project_code",
        ),
        UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_material_stock_locations_scope",
        ),
        CheckConstraint("revision >= 1", name="ck_material_stock_locations_revision"),
        Index(
            "ix_material_stock_locations_project_status",
            "project_id",
            "status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    location_type: Mapped[StockLocationType] = mapped_column(
        Enum(StockLocationType, native_enum=False, values_callable=enum_values),
        default=StockLocationType.SITE_STORE,
    )
    status: Mapped[StockLocationStatus] = mapped_column(
        Enum(StockLocationStatus, native_enum=False, values_callable=enum_values),
        default=StockLocationStatus.ACTIVE,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class MaterialStockTransaction(UUIDTimestampMixin, Base):
    __tablename__ = "material_stock_transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["stock_location_id", "project_id", "organization_id"],
            [
                "material_stock_locations.id",
                "material_stock_locations.project_id",
                "material_stock_locations.organization_id",
            ],
            name="fk_material_stock_transactions_location_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_material_stock_transactions_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_material_stock_transactions_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_material_stock_transactions_boq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_stock_transactions_creator_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "source_type",
            "source_record_id",
            "direction",
            name="uq_material_stock_transactions_source_direction",
        ),
        CheckConstraint("quantity > 0", name="ck_material_stock_transactions_quantity"),
        CheckConstraint(
            "unit_cost_snapshot IS NULL OR unit_cost_snapshot >= 0",
            name="ck_material_stock_transactions_unit_cost",
        ),
        Index(
            "ix_material_stock_transactions_project_location_material",
            "project_id",
            "stock_location_id",
            "material_id",
        ),
        Index(
            "ix_material_stock_transactions_project_occurred",
            "project_id",
            "occurred_at",
        ),
        Index(
            "ix_material_stock_transactions_source",
            "source_type",
            "source_record_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    stock_location_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    material_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    transaction_type: Mapped[StockTransactionType] = mapped_column(
        Enum(StockTransactionType, native_enum=False, values_callable=enum_values)
    )
    direction: Mapped[StockDirection] = mapped_column(
        Enum(StockDirection, native_enum=False, values_callable=enum_values)
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_code: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[StockSourceType] = mapped_column(
        Enum(StockSourceType, native_enum=False, values_callable=enum_values)
    )
    source_record_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    unit_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    created_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
