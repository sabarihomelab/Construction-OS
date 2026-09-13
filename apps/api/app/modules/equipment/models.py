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


class EquipmentStatus(StrEnum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"
    RETIRED = "retired"


class EquipmentOwnership(StrEnum):
    OWNED = "owned"
    RENTED = "rented"
    LEASED = "leased"
    SUBCONTRACTOR = "subcontractor"


class EquipmentAssignmentStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class MaintenanceStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaterialStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class MaterialDeliveryStatus(StrEnum):
    PENDING = "pending"
    RECEIVED = "received"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class EquipmentAsset(UUIDTimestampMixin, Base):
    __tablename__ = "equipment_assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_equipment_assets_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "asset_number", name="uq_equipment_assets_org_number"),
        UniqueConstraint("id", "organization_id", name="uq_equipment_assets_id_org"),
        CheckConstraint("revision >= 1", name="ck_equipment_assets_revision"),
        Index("ix_equipment_assets_org_status", "organization_id", "status"),
        Index("ix_equipment_assets_org_category", "organization_id", "category"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    asset_number: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    make: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ownership: Mapped[EquipmentOwnership] = mapped_column(
        Enum(EquipmentOwnership, native_enum=False, values_callable=enum_values),
        default=EquipmentOwnership.OWNED,
    )
    status: Mapped[EquipmentStatus] = mapped_column(
        Enum(EquipmentStatus, native_enum=False, values_callable=enum_values),
        default=EquipmentStatus.AVAILABLE,
    )
    meter_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_meter: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ProjectEquipmentAssignment(UUIDTimestampMixin, Base):
    __tablename__ = "project_equipment_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_equipment_assignments_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["equipment_asset_id", "organization_id"],
            ["equipment_assets.id", "equipment_assets.organization_id"],
            name="fk_equipment_assignments_asset_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["operator_worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_equipment_assignments_worker_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "equipment_asset_id",
            "start_date",
            name="uq_equipment_assignments_project_asset_start",
        ),
        UniqueConstraint("id", "organization_id", name="uq_equipment_assignments_id_org"),
        UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_equipment_assignments_scope",
        ),
        CheckConstraint("revision >= 1", name="ck_equipment_assignments_revision"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_equipment_assignments_date_range",
        ),
        Index("ix_equipment_assignments_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    equipment_asset_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    operator_worker_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[EquipmentAssignmentStatus] = mapped_column(
        Enum(EquipmentAssignmentStatus, native_enum=False, values_callable=enum_values),
        default=EquipmentAssignmentStatus.ACTIVE,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    starting_meter: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ending_meter: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class EquipmentMaintenance(UUIDTimestampMixin, Base):
    __tablename__ = "equipment_maintenance"
    __table_args__ = (
        ForeignKeyConstraint(
            ["equipment_asset_id", "organization_id"],
            ["equipment_assets.id", "equipment_assets.organization_id"],
            name="fk_equipment_maintenance_asset_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_equipment_maintenance_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_equipment_maintenance_id_org"),
        CheckConstraint("revision >= 1", name="ck_equipment_maintenance_revision"),
        CheckConstraint("meter_value IS NULL OR meter_value >= 0", name="ck_equipment_maintenance_meter"),
        Index("ix_equipment_maintenance_asset_status", "equipment_asset_id", "status", "due_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    equipment_asset_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    maintenance_type: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus, native_enum=False, values_callable=enum_values),
        default=MaintenanceStatus.SCHEDULED,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meter_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    meter_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class Material(UUIDTimestampMixin, Base):
    __tablename__ = "materials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_materials_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "code", name="uq_materials_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_materials_id_org"),
        CheckConstraint("revision >= 1", name="ck_materials_revision"),
        Index("ix_materials_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_unit_code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MaterialStatus] = mapped_column(
        Enum(MaterialStatus, native_enum=False, values_callable=enum_values),
        default=MaterialStatus.ACTIVE,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ProjectMaterialPlan(UUIDTimestampMixin, Base):
    __tablename__ = "project_material_plans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_material_plans_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_material_plans_material_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "material_id", name="uq_material_plans_project_material"),
        UniqueConstraint("id", "organization_id", name="uq_material_plans_id_org"),
        CheckConstraint("planned_quantity >= 0", name="ck_material_plans_quantity"),
        CheckConstraint("revision >= 1", name="ck_material_plans_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    material_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    unit_code: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class MaterialDelivery(UUIDTimestampMixin, Base):
    __tablename__ = "material_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_material_deliveries_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_material_deliveries_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "received_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_deliveries_receiver_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_material_deliveries_id_org"),
        CheckConstraint("quantity > 0", name="ck_material_deliveries_quantity"),
        CheckConstraint("revision >= 1", name="ck_material_deliveries_revision"),
        Index("ix_material_deliveries_project_status", "project_id", "status", "delivered_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    material_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_code: Mapped[str] = mapped_column(String(40))
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ticket_number: Mapped[str | None] = mapped_column(String(160), nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[MaterialDeliveryStatus] = mapped_column(
        Enum(MaterialDeliveryStatus, native_enum=False, values_callable=enum_values),
        default=MaterialDeliveryStatus.PENDING,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
