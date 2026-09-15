from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class KnowledgeSourceKind(StrEnum):
    FILE = "file"
    CONFIGURATION = "configuration"
    MANUAL = "manual"


class KnowledgeSourceStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    RETIRED = "retired"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class TenantKnowledgeSource(UUIDTimestampMixin, Base):
    __tablename__ = "tenant_knowledge_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["file_asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_tenant_knowledge_sources_file_asset_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "key", name="uq_tenant_knowledge_sources_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_tenant_knowledge_sources_id_org"),
        CheckConstraint("source_version >= 1", name="ck_tenant_knowledge_sources_source_version"),
        CheckConstraint(
            "(scope_type IS NULL AND scope_id IS NULL) OR "
            "(scope_type IS NOT NULL AND scope_id IS NOT NULL)",
            name="ck_tenant_knowledge_sources_scope_pair",
        ),
        Index("ix_tenant_knowledge_sources_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(140))
    name: Mapped[str] = mapped_column(String(180))
    kind: Mapped[KnowledgeSourceKind] = mapped_column(
        Enum(KnowledgeSourceKind, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[KnowledgeSourceStatus] = mapped_column(
        Enum(KnowledgeSourceStatus, native_enum=False, values_callable=enum_values),
        default=KnowledgeSourceStatus.PENDING,
    )
    file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    required_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True
    )
    scope_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    failure_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TenantKnowledgeChunk(UUIDTimestampMixin, Base):
    __tablename__ = "tenant_knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["tenant_knowledge_sources.id", "tenant_knowledge_sources.organization_id"],
            name="fk_tenant_knowledge_chunks_source_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "source_id",
            "source_version",
            "ordinal",
            name="uq_tenant_knowledge_chunks_version_ordinal",
        ),
        CheckConstraint("source_version >= 1", name="ck_tenant_knowledge_chunks_source_version"),
        CheckConstraint("ordinal >= 0", name="ck_tenant_knowledge_chunks_ordinal"),
        CheckConstraint(
            "character_count >= 0", name="ck_tenant_knowledge_chunks_character_count"
        ),
        Index("ix_tenant_knowledge_chunks_org_source", "organization_id", "source_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    character_count: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
