from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class DrawingSetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DrawingRevisionStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class DrawingMarkupType(StrEnum):
    TEXT = "text"
    ARROW = "arrow"
    CLOUD = "cloud"
    POLYLINE = "polyline"
    RECTANGLE = "rectangle"
    FREEHAND = "freehand"


class DrawingMeasurementType(StrEnum):
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    COUNT = "count"


class DrawingPinType(StrEnum):
    RFI = "rfi"
    PHOTO = "photo"
    PUNCH = "punch"
    INSPECTION = "inspection"
    SUBMITTAL = "submittal"
    CUSTOM = "custom"


class DrawingComparisonStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class DrawingSet(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_sets"
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_drawing_sets_project_org", ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_drawing_sets_id_org"),
        UniqueConstraint("project_id", "name", name="uq_drawing_sets_project_name"),
        CheckConstraint("version >= 1", name="ck_drawing_sets_version"),
        Index("ix_drawing_sets_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DrawingSetStatus] = mapped_column(Enum(DrawingSetStatus, native_enum=False, values_callable=enum_values), default=DrawingSetStatus.ACTIVE)
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class DrawingSheet(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_sheets"
    __table_args__ = (
        ForeignKeyConstraint(["drawing_set_id", "organization_id"], ["drawing_sets.id", "drawing_sets.organization_id"], name="fk_drawing_sheets_set_org", ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_drawing_sheets_id_org"),
        UniqueConstraint("drawing_set_id", "sheet_number", name="uq_drawing_sheets_set_number"),
        CheckConstraint("version >= 1", name="ck_drawing_sheets_version"),
        CheckConstraint("current_revision_sequence >= 0", name="ck_drawing_sheets_current_revision"),
        Index("ix_drawing_sheets_set_discipline", "drawing_set_id", "discipline_code"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    drawing_set_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sheet_number: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(500))
    discipline_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    current_revision_sequence: Mapped[int] = mapped_column(Integer, default=0)


class DrawingRevision(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["sheet_id", "organization_id"], ["drawing_sheets.id", "drawing_sheets.organization_id"], name="fk_drawing_revisions_sheet_org", ondelete="CASCADE"),
        ForeignKeyConstraint(["file_version_id", "organization_id"], ["file_versions.id", "file_versions.organization_id"], name="fk_drawing_revisions_file_org", ondelete="RESTRICT"),
        ForeignKeyConstraint(["document_revision_id", "organization_id"], ["document_revisions.id", "document_revisions.organization_id"], name="fk_drawing_revisions_document_revision_org", ondelete="RESTRICT"),
        UniqueConstraint("id", "organization_id", name="uq_drawing_revisions_id_org"),
        UniqueConstraint("sheet_id", "sequence", name="uq_drawing_revisions_sheet_sequence"),
        UniqueConstraint("sheet_id", "revision_label", name="uq_drawing_revisions_sheet_label"),
        CheckConstraint("sequence >= 1", name="ck_drawing_revisions_sequence"),
        CheckConstraint("source_page >= 1", name="ck_drawing_revisions_source_page"),
        CheckConstraint("render_version >= 1", name="ck_drawing_revisions_render_version"),
        Index("ix_drawing_revisions_sheet_status", "sheet_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sheet_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    revision_label: Mapped[str] = mapped_column(String(80))
    file_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    document_revision_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_page: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[DrawingRevisionStatus] = mapped_column(Enum(DrawingRevisionStatus, native_enum=False, values_callable=enum_values), default=DrawingRevisionStatus.DRAFT)
    render_version: Mapped[int] = mapped_column(Integer, default=1)
    renderer_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    page_width: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    page_height: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    geometry_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DrawingRenderPackage(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_render_packages"
    __table_args__ = (
        ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_render_packages_revision_org", ondelete="CASCADE"),
        UniqueConstraint("drawing_revision_id", "render_version", name="uq_drawing_render_packages_revision_version"),
        CheckConstraint("render_version >= 1", name="ck_drawing_render_packages_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    drawing_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    render_version: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DrawingCalibration(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_calibrations"
    __table_args__ = (
        ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_calibrations_revision_org", ondelete="CASCADE"),
        UniqueConstraint("drawing_revision_id", "version", name="uq_drawing_calibrations_revision_version"),
        CheckConstraint("version >= 1", name="ck_drawing_calibrations_version"),
        CheckConstraint("real_length > 0", name="ck_drawing_calibrations_real_length"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    drawing_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    point_a_x: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    point_a_y: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    point_b_x: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    point_b_y: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    real_length: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    unit_code: Mapped[str] = mapped_column(String(32))
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DrawingMarkup(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_markups"
    __table_args__ = (
        ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_markups_revision_org", ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_drawing_markups_id_org"),
        CheckConstraint("version >= 1", name="ck_drawing_markups_version"),
        Index("ix_drawing_markups_revision_type", "drawing_revision_id", "markup_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    drawing_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    markup_type: Mapped[DrawingMarkupType] = mapped_column(Enum(DrawingMarkupType, native_enum=False, values_callable=enum_values))
    geometry: Mapped[dict[str, object]] = mapped_column(JSONB)
    style: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DrawingMeasurement(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_measurements"
    __table_args__ = (
        ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_measurements_revision_org", ondelete="CASCADE"),
        ForeignKeyConstraint(["calibration_id", "organization_id"], ["drawing_calibrations.id", "drawing_calibrations.organization_id"], name="fk_drawing_measurements_calibration_org", ondelete="RESTRICT"),
        CheckConstraint("value >= 0", name="ck_drawing_measurements_value"),
        CheckConstraint("version >= 1", name="ck_drawing_measurements_version"),
        Index("ix_drawing_measurements_revision_type", "drawing_revision_id", "measurement_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    drawing_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    calibration_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    measurement_type: Mapped[DrawingMeasurementType] = mapped_column(Enum(DrawingMeasurementType, native_enum=False, values_callable=enum_values))
    geometry: Mapped[dict[str, object]] = mapped_column(JSONB)
    value: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    unit_code: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DrawingPin(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_pins"
    __table_args__ = (
        ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_pins_revision_org", ondelete="CASCADE"),
        CheckConstraint("x >= 0 AND x <= 1", name="ck_drawing_pins_x"),
        CheckConstraint("y >= 0 AND y <= 1", name="ck_drawing_pins_y"),
        CheckConstraint("version >= 1", name="ck_drawing_pins_version"),
        Index("ix_drawing_pins_revision_type", "drawing_revision_id", "pin_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    drawing_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    pin_type: Mapped[DrawingPinType] = mapped_column(Enum(DrawingPinType, native_enum=False, values_callable=enum_values))
    target_entity_type: Mapped[str] = mapped_column(String(100))
    target_entity_id: Mapped[str] = mapped_column(String(160))
    x: Mapped[Decimal] = mapped_column(Numeric(12, 10))
    y: Mapped[Decimal] = mapped_column(Numeric(12, 10))
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DrawingComparison(UUIDTimestampMixin, Base):
    __tablename__ = "drawing_comparisons"
    __table_args__ = (
        ForeignKeyConstraint(["base_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_comparisons_base_org", ondelete="CASCADE"),
        ForeignKeyConstraint(["compare_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_comparisons_compare_org", ondelete="CASCADE"),
        UniqueConstraint("base_revision_id", "compare_revision_id", name="uq_drawing_comparisons_pair"),
        CheckConstraint("base_revision_id <> compare_revision_id", name="ck_drawing_comparisons_distinct"),
        Index("ix_drawing_comparisons_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    base_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    compare_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[DrawingComparisonStatus] = mapped_column(Enum(DrawingComparisonStatus, native_enum=False, values_callable=enum_values), default=DrawingComparisonStatus.QUEUED)
    alignment: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_manifest: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
