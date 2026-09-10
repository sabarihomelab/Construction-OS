from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class DocumentKind(StrEnum):
    GENERAL = "general"
    SPECIFICATION = "specification"
    CONTRACT = "contract"
    PROCEDURE = "procedure"
    CLOSEOUT = "closeout"
    OTHER = "other"


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentRevisionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    VOID = "void"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class DocumentFolder(UUIDTimestampMixin, Base):
    __tablename__ = "document_folders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_document_folders_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id", "organization_id"],
            ["document_folders.id", "document_folders.organization_id"],
            name="fk_document_folders_parent_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_document_folders_id_org"),
        UniqueConstraint("project_id", "parent_id", "name", name="uq_document_folders_parent_name"),
        Index("ix_document_folders_project_parent", "project_id", "parent_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Document(UUIDTimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_documents_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["folder_id", "organization_id"],
            ["document_folders.id", "document_folders.organization_id"],
            name="fk_documents_folder_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_documents_id_org"),
        UniqueConstraint("project_id", "number", name="uq_documents_project_number"),
        CheckConstraint("version >= 1", name="ck_documents_version"),
        CheckConstraint("current_revision_sequence >= 0", name="ck_documents_current_revision"),
        Index("ix_documents_project_kind_status", "project_id", "kind", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    folder_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    number: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[DocumentKind] = mapped_column(
        Enum(DocumentKind, native_enum=False, values_callable=enum_values),
        default=DocumentKind.GENERAL,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, values_callable=enum_values),
        default=DocumentStatus.DRAFT,
    )
    discipline_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    current_revision_sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DocumentRevision(UUIDTimestampMixin, Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name="fk_document_revisions_document_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_version_id", "organization_id"],
            ["file_versions.id", "file_versions.organization_id"],
            name="fk_document_revisions_file_version_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_document_revisions_id_org"),
        UniqueConstraint("document_id", "sequence", name="uq_document_revisions_document_sequence"),
        UniqueConstraint("document_id", "revision_label", name="uq_document_revisions_document_label"),
        CheckConstraint("sequence >= 1", name="ck_document_revisions_sequence"),
        Index("ix_document_revisions_document_status", "document_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    revision_label: Mapped[str] = mapped_column(String(80))
    file_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[DocumentRevisionStatus] = mapped_column(
        Enum(DocumentRevisionStatus, native_enum=False, values_callable=enum_values),
        default=DocumentRevisionStatus.DRAFT,
    )
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpecificationSection(UUIDTimestampMixin, Base):
    __tablename__ = "specification_sections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name="fk_specification_sections_document_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_specification_sections_id_org"),
        UniqueConstraint("document_id", "section_number", name="uq_specification_sections_number"),
        CheckConstraint("version >= 1", name="ck_specification_sections_version"),
        CheckConstraint(
            "page_start IS NULL OR page_start >= 1",
            name="ck_specification_sections_page_start",
        ),
        CheckConstraint(
            "page_end IS NULL OR page_end >= 1",
            name="ck_specification_sections_page_end",
        ),
        Index("ix_specification_sections_document_number", "document_id", "section_number"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    section_number: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(500))
    division_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
