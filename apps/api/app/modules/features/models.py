from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationFeature(Base):
    __tablename__ = "organization_features"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_organization_features_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    feature_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
