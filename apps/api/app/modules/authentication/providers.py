from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.sessions.models import AuthenticationLevel, AuthenticationMethod


@dataclass(frozen=True, slots=True)
class AuthenticationAssertion:
    provider_key: str
    subject: str
    email: str
    email_verified: bool
    display_name: str
    method: AuthenticationMethod
    level: AuthenticationLevel
    authenticated_at: datetime
    mfa_verified_at: datetime | None = None


class AuthenticationProvider(Protocol):
    provider_key: str

    async def authenticate(
        self,
        payload: Mapping[str, object],
    ) -> AuthenticationAssertion: ...


class AuthenticationProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AuthenticationProvider] = {}

    def register(self, provider: AuthenticationProvider) -> None:
        key = provider.provider_key.strip()
        if not key:
            raise ValueError("Authentication provider key is required")
        if key in self._providers:
            raise ValueError(f"Authentication provider already registered: {key}")
        self._providers[key] = provider

    def get(self, key: str) -> AuthenticationProvider:
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ValueError(f"Unknown authentication provider: {key}") from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


AUTHENTICATION_PROVIDERS = AuthenticationProviderRegistry()
AuthenticationCallback = Awaitable[AuthenticationAssertion]
