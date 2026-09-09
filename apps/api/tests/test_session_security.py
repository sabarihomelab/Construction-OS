from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.sessions.service import generate_secret, hash_secret, validate_csrf_token


def test_session_table_never_stores_raw_tokens() -> None:
    table = Base.metadata.tables["sessions"]
    assert "token" not in table.c
    assert "csrf_token" not in table.c
    assert table.c.token_hash.type.length == 64
    assert table.c.csrf_token_hash.type.length == 64


def test_generated_session_secrets_are_distinct_and_hashed() -> None:
    first = generate_secret()
    second = generate_secret()
    assert first != second
    assert len(hash_secret(first)) == 64
    assert first != hash_secret(first)


def test_csrf_token_is_bound_to_server_session_hash() -> None:
    raw_token = generate_secret()
    session = SimpleNamespace(csrf_token_hash=hash_secret(raw_token))
    assert validate_csrf_token(session, raw_token)
    assert not validate_csrf_token(session, generate_secret())


def test_default_idle_timeout_is_three_minutes() -> None:
    settings = Settings(_env_file=None)
    assert settings.session_idle_timeout_seconds == 180


def test_production_rejects_insecure_session_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", session_cookie_secure=False, _env_file=None)
