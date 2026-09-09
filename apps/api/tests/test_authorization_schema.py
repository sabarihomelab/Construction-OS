from sqlalchemy import BigInteger

from app.db import model_registry  # noqa: F401
from app.db.base import Base


def test_authorization_tables_are_registered() -> None:
    expected = {
        "permissions",
        "roles",
        "role_permissions",
        "membership_roles",
        "organization_authorization_state",
    }
    assert expected.issubset(Base.metadata.tables.keys())


def test_permissions_use_stable_string_key() -> None:
    permission_key = Base.metadata.tables["permissions"].c.key
    assert permission_key.primary_key
    assert permission_key.type.length == 160


def test_role_permission_presence_represents_allow() -> None:
    table = Base.metadata.tables["role_permissions"]
    assert "effect" not in table.c
    assert {"role_id", "permission_key"} == {column.name for column in table.primary_key.columns}


def test_membership_role_assignment_is_composite_key() -> None:
    table = Base.metadata.tables["membership_roles"]
    assert {"membership_id", "role_id"} == {column.name for column in table.primary_key.columns}


def test_authorization_revision_can_scale() -> None:
    column = Base.metadata.tables["organization_authorization_state"].c.revision
    assert isinstance(column.type, BigInteger)
