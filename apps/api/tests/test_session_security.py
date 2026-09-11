from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.sessions.deps import (
    SessionTransport,
    _session_token_from_request,
    require_csrf,
)
from app.modules.sessions.service import generate_secret, hash_secret, validate_csrf_token


def _request(
    *,
    authorization: str | None = None,
    cookie: str | None = None,
    csrf: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    if cookie is not None:
        headers.append((b"cookie", f"construction_os_session={cookie}".encode()))
    if csrf is not None:
        headers.append((b"x-csrf-token", csrf.encode()))
    return Request({"type": "http", "headers": headers})


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


def test_cookie_session_transport_is_preserved() -> None:
    token, transport = _session_token_from_request(_request(cookie="browser-token"))
    assert token == "browser-token"
    assert transport == SessionTransport.COOKIE


def test_bearer_session_transport_is_accepted_and_preferred() -> None:
    token, transport = _session_token_from_request(
        _request(authorization="Bearer native-token", cookie="browser-token")
    )
    assert token == "native-token"
    assert transport == SessionTransport.BEARER


@pytest.mark.parametrize(
    "authorization",
    ["", "Basic abc", "Bearer", "Bearer ", "Bearer token extra"],
)
def test_invalid_authorization_never_falls_back_to_cookie(authorization: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _session_token_from_request(
            _request(authorization=authorization, cookie="browser-token")
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_cookie_authenticated_mutation_requires_csrf() -> None:
    csrf = generate_secret()
    session = SimpleNamespace(csrf_token_hash=hash_secret(csrf))
    request = _request(cookie="browser-token")
    request.state.session_transport = SessionTransport.COOKIE

    with pytest.raises(HTTPException) as exc_info:
        await require_csrf(request, session)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_cookie_authenticated_mutation_accepts_matching_csrf() -> None:
    csrf = generate_secret()
    session = SimpleNamespace(csrf_token_hash=hash_secret(csrf))
    request = _request(cookie="browser-token", csrf=csrf)
    request.state.session_transport = SessionTransport.COOKIE

    await require_csrf(request, session)


@pytest.mark.asyncio
async def test_bearer_authenticated_mutation_does_not_require_csrf() -> None:
    session = SimpleNamespace(csrf_token_hash=hash_secret(generate_secret()))
    request = _request(authorization="Bearer native-token")
    request.state.session_transport = SessionTransport.BEARER

    await require_csrf(request, session)


def test_default_idle_timeout_is_three_minutes() -> None:
    settings = Settings(_env_file=None)
    assert settings.session_idle_timeout_seconds == 180


def test_production_rejects_insecure_session_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", session_cookie_secure=False, _env_file=None)
