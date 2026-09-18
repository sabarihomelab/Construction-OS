from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class FinancialRuleSnapshot(UUIDTimestampMixin, Base):
    __tablename__ = "financial_rule_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_financial_rule_snapshots_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            "rule_key",
            name="uq_financial_rule_snapshots_entity_rule",
        ),
        Index(
            "ix_financial_rule_snapshots_project_entity",
            "project_id",
            "entity_type",
            "entity_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rule_key: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(40))
    version: Mapped[int | None] = mapped_column(nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
