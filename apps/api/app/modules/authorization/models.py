from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class PermissionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RoleAssignmentScope(StrEnum):
    COMPANY = "company"
    PROJECT = "project"
    BOTH = "both"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Permission(Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    module: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    risk: Mapped[PermissionRisk] = mapped_column(
        Enum(PermissionRisk, native_enum=False, values_callable=enum_values),
        default=PermissionRisk.LOW,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(UUIDTimestampMixin, Base):
    __tablename__ = "roles"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_scope: Mapped[RoleAssignmentScope] = mapped_column(
        Enum(RoleAssignmentScope, native_enum=False, values_callable=enum_values),
        default=RoleAssignmentScope.BOTH,
    )
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_roles_id_org"),
        Index(
            "uq_roles_org_key",
            "organization_id",
            "key",
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
        Index(
            "uq_roles_system_template_key",
            "key",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_key: Mapped[str] = mapped_column(
        ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )


class MembershipRole(Base):
    __tablename__ = "membership_roles"
    __table_args__ = (
        UniqueConstraint("membership_id", "role_id", name="uq_membership_roles_membership_role"),
    )

    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class MembershipPartyAffiliation(Base):
    __tablename__ = "membership_party_affiliations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_membership_party_affiliation_membership_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_membership_party_affiliation_party_org",
            ondelete="RESTRICT",
        ),
        Index("ix_membership_party_affiliations_org_party", "organization_id", "party_id"),
    )

    membership_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    party_id: Mapped[UUID] = mapped_column(Uuid, index=True)


class OrganizationAuthorizationState(Base):
    __tablename__ = "organization_authorization_state"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
