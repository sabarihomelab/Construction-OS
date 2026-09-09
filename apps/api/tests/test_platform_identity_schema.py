from sqlalchemy import BigInteger

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.identity.schemas import UserCreate


def test_platform_identity_tables_are_registered() -> None:
    expected = {
        "organizations",
        "organization_settings",
        "users",
        "user_preferences",
        "organization_memberships",
    }
    assert expected.issubset(Base.metadata.tables.keys())


def test_storage_quota_uses_bigint() -> None:
    column = Base.metadata.tables["organization_settings"].c.storage_quota_bytes
    assert isinstance(column.type, BigInteger)


def test_membership_is_unique_per_organization_and_user() -> None:
    table = Base.metadata.tables["organization_memberships"]
    unique_names = {constraint.name for constraint in table.constraints if constraint.name}
    assert "uq_organization_memberships_org_user" in unique_names


def test_user_email_is_normalized() -> None:
    payload = UserCreate(primary_email="  ADMIN@Example.COM ", display_name="Admin")
    assert str(payload.primary_email) == "admin@example.com"
