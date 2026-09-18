from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PurchaseOrderRevision(Base):
    __tablename__ = "purchase_order_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_purchase_order_revisions_po_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "purchase_order_id",
            "version_number",
            name="uq_purchase_order_revisions_version",
        ),
        CheckConstraint("version_number >= 1", name="ck_purchase_order_revisions_version"),
    )

    purchase_order_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    superseded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
