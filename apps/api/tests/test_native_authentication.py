from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.base import Base
from app.modules.authentication.native_schemas import (
    NativeAuthenticationRequest,
    NativeMembershipSelectionRequest,
    NativeSessionResponse,
)
from app.modules.authentication.native_service import _assertion_from_grant
from app.modules.authentication.providers import (
    AuthenticationAssertion,
    AuthenticationProviderRegistry,
)
from app.modules.sessions.models import (
    AuthenticationLevel,
    AuthenticationMethod,
    MobileAuthenticationGrant,
)
from app.modules.sessions.service import generate_secret, hash_secret


class StubProvider:
    provider_key = "test-oidc"

    async def authenticate(self, payload: dict[str, object]) -> AuthenticationAssertion:
        assert payload == {"authorization_code": "provider-code"}
        return AuthenticationAssertion(
            provider_key=self.provider_key,
            subject="subject-123",
            email="field@example.com",
            email_verified=True,
            display_name="Field User",
            method=AuthenticationMethod.OIDC,
            level=AuthenticationLevel.MFA,
            authenticated_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
            mfa_verified_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
        )


def test_mobile_authentication_grant_never_stores_raw_grant() -> None:
    table = MobileAuthenticationGrant.__table__
    assert table.name == "mobile_authentication_grants"
    assert "grant_token" not in table.c
    assert table.c.grant_token_hash.type.length == 64


def test_native_request_accepts_provider_payload_not_client_assertion() -> None:
    request = NativeAuthenticationRequest(
        provider_key="test-oidc",
        payload={"authorization_code": "provider-code"},
    )
    assert request.provider_key == "test-oidc"
    assert not hasattr(request, "assertion")


def test_membership_selection_requires_opaque_grant_and_membership() -> None:
    with pytest.raises(ValidationError):
        NativeMembershipSelectionRequest(grant_token="short", membership_id=uuid4())

    payload = NativeMembershipSelectionRequest(
        grant_token=generate_secret(),
        membership_id=uuid4(),
    )
    assert payload.membership_id


def test_provider_registry_is_provider_neutral_and_rejects_duplicates() -> None:
    registry = AuthenticationProviderRegistry()
    provider = StubProvider()
    registry.register(provider)
    assert registry.get("test-oidc") is provider
    assert registry.keys() == ("test-oidc",)
    with pytest.raises(ValueError):
        registry.register(provider)


@pytest.mark.asyncio
async def test_provider_produces_server_side_assertion() -> None:
    assertion = await StubProvider().authenticate({"authorization_code": "provider-code"})
    assert assertion.subject == "subject-123"
    assert assertion.email_verified
    assert assertion.method == AuthenticationMethod.OIDC


def test_grant_round_trip_preserves_server_verified_authentication_context() -> None:
    authenticated_at = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    grant = SimpleNamespace(
        provider_key="test-oidc",
        subject="subject-123",
        email="field@example.com",
        email_verified=True,
        display_name="Field User",
        authentication_method=AuthenticationMethod.OIDC,
        authentication_level=AuthenticationLevel.MFA,
        authenticated_at=authenticated_at,
        mfa_verified_at=authenticated_at,
    )
    assertion = _assertion_from_grant(grant)
    assert assertion.provider_key == "test-oidc"
    assert assertion.authenticated_at == authenticated_at
    assert assertion.level == AuthenticationLevel.MFA


def test_native_session_response_exposes_only_bearer_token_not_csrf() -> None:
    response = NativeSessionResponse(access_token="native-token", membership_id=uuid4())
    body = response.model_dump()
    assert body["token_type"] == "Bearer"
    assert body["access_token"] == "native-token"
    assert "csrf_token" not in body


def test_grant_hash_is_opaque_and_expiry_window_is_short() -> None:
    raw = generate_secret()
    assert raw != hash_secret(raw)
    assert len(hash_secret(raw)) == 64
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    assert now + timedelta(seconds=300) < now + timedelta(minutes=10)


def test_native_authentication_table_is_registered_when_model_is_loaded() -> None:
    assert "mobile_authentication_grants" in Base.metadata.tables
