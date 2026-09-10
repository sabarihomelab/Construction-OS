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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class EstimateStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class RateComponentKind(StrEnum):
    MATERIAL = "material"
    LABOUR = "labour"
    EQUIPMENT = "equipment"
    SUBCONTRACT = "subcontract"
    OVERHEAD = "overhead"
    OTHER = "other"


class BudgetStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class BudgetCategory(StrEnum):
    MATERIAL = "material"
    LABOUR = "labour"
    EQUIPMENT = "equipment"
    SUBCONTRACT = "subcontract"
    OVERHEAD = "overhead"
    OTHER = "other"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ProjectEstimate(UUIDTimestampMixin, Base):
    __tablename__ = "project_estimates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_estimates_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_boq_id", "project_id", "organization_id"],
            ["project_boqs.id", "project_boqs.project_id", "project_boqs.organization_id"],
            name="fk_project_estimates_boq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_estimates_approved_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_project_estimates_project_code"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_project_estimates_scope"),
        CheckConstraint("revision >= 1", name="ck_project_estimates_revision"),
        Index("ix_project_estimates_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_boq_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[EstimateStatus] = mapped_column(
        Enum(EstimateStatus, native_enum=False, values_callable=enum_values),
        default=EstimateStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EstimateItem(UUIDTimestampMixin, Base):
    __tablename__ = "estimate_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_items_estimate_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_estimate_items_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_estimate_items_boq_item_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("estimate_id", "line_number", name="uq_estimate_items_line"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_estimate_items_scope"),
        CheckConstraint("quantity >= 0", name="ck_estimate_items_quantity"),
        CheckConstraint("rate >= 0", name="ck_estimate_items_rate"),
        CheckConstraint("amount >= 0", name="ck_estimate_items_amount"),
        CheckConstraint("revision >= 1", name="ck_estimate_items_revision"),
        Index("ix_estimate_items_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    estimate_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class RateAnalysis(UUIDTimestampMixin, Base):
    __tablename__ = "rate_analyses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["estimate_item_id", "project_id", "organization_id"],
            ["estimate_items.id", "estimate_items.project_id", "estimate_items.organization_id"],
            name="fk_rate_analyses_estimate_item_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint("estimate_item_id", "version_number", name="uq_rate_analysis_item_version"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_rate_analyses_scope"),
        CheckConstraint("version_number >= 1", name="ck_rate_analyses_version"),
        CheckConstraint("wastage_percent >= 0", name="ck_rate_analyses_wastage"),
        CheckConstraint("overhead_percent >= 0", name="ck_rate_analyses_overhead"),
        CheckConstraint("profit_percent >= 0", name="ck_rate_analyses_profit"),
        CheckConstraint("calculated_rate >= 0", name="ck_rate_analyses_rate"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    estimate_item_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    wastage_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal(0))
    overhead_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal(0))
    profit_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal(0))
    calculated_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    is_current: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RateAnalysisComponent(UUIDTimestampMixin, Base):
    __tablename__ = "rate_analysis_components"
    __table_args__ = (
        ForeignKeyConstraint(
            ["analysis_id", "project_id", "organization_id"],
            ["rate_analyses.id", "rate_analyses.project_id", "rate_analyses.organization_id"],
            name="fk_rate_components_analysis_scope",
            ondelete="CASCADE",
        ),
        CheckConstraint("quantity >= 0", name="ck_rate_components_quantity"),
        CheckConstraint("unit_rate >= 0", name="ck_rate_components_unit_rate"),
        CheckConstraint("amount >= 0", name="ck_rate_components_amount"),
        Index("ix_rate_components_analysis_kind", "analysis_id", "kind"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    analysis_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[RateComponentKind] = mapped_column(
        Enum(RateComponentKind, native_enum=False, values_callable=enum_values)
    )
    description: Mapped[str] = mapped_column(String(255))
    unit_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(1))
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    source_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class ProjectBudget(UUIDTimestampMixin, Base):
    __tablename__ = "project_budgets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_budgets_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_project_budgets_estimate_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_budgets_approved_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_project_budgets_project_code"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_project_budgets_scope"),
        CheckConstraint("revision >= 1", name="ck_project_budgets_revision"),
        Index("ix_project_budgets_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    estimate_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[BudgetStatus] = mapped_column(
        Enum(BudgetStatus, native_enum=False, values_callable=enum_values),
        default=BudgetStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BudgetLine(UUIDTimestampMixin, Base):
    __tablename__ = "project_budget_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["budget_id", "project_id", "organization_id"],
            ["project_budgets.id", "project_budgets.project_id", "project_budgets.organization_id"],
            name="fk_budget_lines_budget_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_budget_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("budget_id", "wbs_code_id", "category", name="uq_budget_line_dimension"),
        CheckConstraint("amount >= 0", name="ck_budget_lines_amount"),
        CheckConstraint("revision >= 1", name="ck_budget_lines_revision"),
        Index("ix_budget_lines_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    budget_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    category: Mapped[BudgetCategory] = mapped_column(
        Enum(BudgetCategory, native_enum=False, values_callable=enum_values)
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
