from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class SearchDocument(UUIDTimestampMixin, Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            name="uq_search_documents_org_entity",
        ),
        CheckConstraint(
            "entity_version IS NULL OR entity_version >= 1",
            name="ck_search_documents_entity_version",
        ),
        CheckConstraint(
            "(scope_type IS NULL AND scope_id IS NULL) OR "
            "(scope_type IS NOT NULL AND scope_id IS NOT NULL)",
            name="ck_search_documents_scope_pair",
        ),
        Index("ix_search_documents_org_type", "organization_id", "entity_type"),
        Index("ix_search_documents_org_scope", "organization_id", "scope_type", "scope_id"),
        Index("ix_search_documents_vector", "search_vector", postgresql_using="gin"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str] = mapped_column(String(160), index=True)
    entity_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    required_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True, index=True
    )
    scope_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    keywords_text: Mapped[str] = mapped_column(Text, default="")
    route_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(subtitle, '')), 'B') || "
            "setweight(to_tsvector('simple', coalesce(keywords_text, '')), 'B') || "
            "setweight(to_tsvector('simple', coalesce(body, '')), 'C')",
            persisted=True,
        ),
    )
