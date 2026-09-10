from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CLOSEOUT = "closeout"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class ProjectMembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Project(UUIDTimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "number", name="uq_projects_org_number"),
        UniqueConstraint("id", "organization_id", name="uq_projects_id_org"),
        CheckConstraint("revision >= 1", name="ck_projects_revision"),
        Index("ix_projects_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, native_enum=False, values_callable=enum_values),
        default=ProjectStatus.PLANNING,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    unit_system: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)


class ProjectMembership(UUIDTimestampMixin, Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_memberships_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_memberships_org_membership_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "project_id",
            "organization_membership_id",
            name="uq_project_memberships_project_membership",
        ),
        UniqueConstraint(
            "project_id",
            "organization_membership_id",
            "organization_id",
            name="uq_project_memberships_project_member_org",
        ),
        UniqueConstraint("id", "organization_id", name="uq_project_memberships_id_org"),
        Index("ix_project_memberships_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    organization_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[ProjectMembershipStatus] = mapped_column(
        Enum(ProjectMembershipStatus, native_enum=False, values_callable=enum_values),
        default=ProjectMembershipStatus.ACTIVE,
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)


class ProjectRoleAssignment(UUIDTimestampMixin, Base):
    __tablename__ = "project_role_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_membership_id", "organization_id"],
            ["project_memberships.id", "project_memberships.organization_id"],
            name="fk_project_role_assignments_membership_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["role_id", "organization_id"],
            ["roles.id", "roles.organization_id"],
            name="fk_project_role_assignments_role_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "project_membership_id", "role_id", name="uq_project_role_assignments_membership_role"
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    role_id: Mapped[UUID] = mapped_column(Uuid, index=True)
